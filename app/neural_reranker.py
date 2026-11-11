"""Rank document evidence with a *real* cross-encoder when explicitly enabled.

The model selects relevant citations; its score is NOT a supplier quality score
and never changes PASS/FAIL/UNKNOWN determined by rule-based checks.

Production defaults to lexical retrieval (small Render free instances cannot
reliably run torch). Set EVIDENCE_RERANKER=cross_encoder and install
requirements-reranker.txt on a CPU instance with adequate memory to enable.
"""
from __future__ import annotations

import os
import re
from typing import Any

_TOKEN = re.compile(r"[a-zа-яё0-9]{2,}",re.I)
_MODEL = None
_MODEL_ID = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

def mode() -> str:
    return os.getenv("EVIDENCE_RERANKER","lexical").strip().lower()

def _lexical(query: str, snippet: str) -> float:
    a=set(_TOKEN.findall(query.casefold()))
    b=set(_TOKEN.findall(snippet.casefold()))
    return len(a & b)/max(len(a),1)

def _model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import CrossEncoder
        # Model is downloaded at first use. Pin the model in production after evaluation.
        _MODEL=CrossEncoder(os.getenv("EVIDENCE_MODEL",_MODEL_ID),device="cpu")
    return _MODEL

def _candidate_lines(text: str, max_lines:int=120) -> list[dict[str,Any]]:
    current="строка"
    lines=[]
    for i,raw in enumerate(text.splitlines(),1):
        line=raw.strip()
        if not line:continue
        if line.lower().startswith("страница ") and line.endswith(":"):
            current=line[:-1]
            continue
        if line.startswith("Лист: "):
            current=line[:100]
            continue
        if len(line)<4:continue
        lines.append({"quote":line[:450],"line":i,"location":current})
        if len(lines)>=max_lines:break
    return lines

def rerank_evidence(result:dict[str,Any],offers:list[tuple[str,str]],
                    max_checks:int=40,top_k:int=3) -> dict[str,Any]:
    """Attach top evidence snippets. Does not certify facts or override decisions."""
    selected_mode=mode()
    neural=selected_mode=="cross_encoder"
    if selected_mode not in ("cross_encoder","lexical"):
        raise ValueError("EVIDENCE_RERANKER must be lexical or cross_encoder")
    candidates=[]
    for supplier in result.get("suppliers",[]):
        text=next((body for name,body in offers if name==supplier.get("name")),"")
        lines=_candidate_lines(text)
        if not lines:continue
        # Prioritize unverified checks and avoid unbounded CPU/GPU costs.
        checks=sorted(supplier.get("checks",[]),
                      key=lambda c:(c.get("status")!="unknown",not c.get("mandatory",True)))
        for check in checks[:max_checks]:
            question=(str(check.get("parameter") or "")+" "+
                      str(check.get("requirement_source") or ""))[:450]
            if not question.strip():continue
            shortlist=sorted(lines,key=lambda x:_lexical(question,x["quote"]),reverse=True)[:8]
            if shortlist:
                candidates.append((supplier["name"],check,question,shortlist))
    if not candidates:
        return {"mode":"none","model":None,"results":[],"note":"Нет фрагментов для сопоставления"}
    # For a low-RAM pilot, bound the cross-encoder to at most 48 requirement groups.
    candidates=candidates[:48]
    pair_batch=[]
    spans=[]
    for supplier,check,question,shortlist in candidates:
        start=len(pair_batch)
        pair_batch.extend([(question,item["quote"]) for item in shortlist])
        spans.append((supplier,check,shortlist,start,len(pair_batch)))
    scores=None
    if neural:
        try:
            predictor=_model()
            values=predictor.predict(pair_batch,batch_size=8,show_progress_bar=False)
            scores=[float(s) for s in values]
            if len(scores)!=len(pair_batch):raise ValueError("Model returned incomplete predictions")
        except (ImportError,OSError,RuntimeError,ValueError) as exc:
            return {"mode":"unavailable","model":os.getenv("EVIDENCE_MODEL",_MODEL_ID),
                    "results":[],"note":"Cross-Encoder не запустился; числовые проверки не изменены"}
    else:
        scores=[_lexical(q,t) for q,t in pair_batch]
    out=[]
    for supplier,check,shortlist,start,end in spans:
        scored=sorted(zip(shortlist,scores[start:end]),key=lambda x:-x[1])[:top_k]
        out.append({"supplier":supplier,"parameter":str(check.get("parameter"))[:120],
                    "requirement_source":str(check.get("requirement_source") or "")[:300],
                    "fragments":[{"quote":x["quote"],"line":x["line"],
                                  "location":x["location"],"relevance_score":round(score,4)}
                                 for x,score in scored]})
    return {"mode":"cross_encoder" if neural else "lexical",
            "model":os.getenv("EVIDENCE_MODEL",_MODEL_ID) if neural else None,
            "results":out,"note":"Оценки означают релевантность текста, не вероятность соответствия"}
