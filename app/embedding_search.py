"""Semantic evidence retrieval using intfloat/multilingual-e5-small.

Only selects source snippets; it never changes PASS / FAIL / UNKNOWN.
Supports a separate private HTTP inference service or a local CPU model.
Both paths use the official E5 query:/passage: prefixes and normalized vectors.
"""
from __future__ import annotations
import math
import os
import re
from typing import Any

_MODEL_ID = "intfloat/multilingual-e5-small"
_LOCAL_MODEL = None
_SECTION = re.compile(r"^(?:Страница\s+\d+:|Лист:\s*.+)$", re.I)
_TOKENS = re.compile(r"\S+")


def split_passages(text: str, max_chars: int = 840, overlap: int = 100,
                   max_passages: int = 400) -> list[dict[str, Any]]:
    """Preserve source line/page and chunk very long lines without losing content.

    Character limit is intentionally conservative vs E5's 512-token window.
    Embedding model truncation must still be monitored for pathological strings.
    """
    out = []
    location = "строка"
    for index, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if _SECTION.fullmatch(line):
            location = line[:-1] if line.endswith(":") else line
            continue
        # Keep a single original row/paragraph intact if possible. Carry
        # overlap for lines that exceed max_chars, preserving their line number.
        pos = 0
        while pos < len(line):
            part = line[pos:pos + max_chars].strip()
            if part:
                out.append({"quote": part, "line": index, "location": location})
            if len(out) >= max_passages:
                return out
            if pos + max_chars >= len(line):
                break
            pos += max_chars - overlap
    return out


def _normalized(values: list[float]) -> list[float]:
    if not values:
        raise ValueError("Empty embedding")
    vector = [float(x) for x in values]
    if any(not math.isfinite(x) for x in vector):
        raise ValueError("Non-finite embedding")
    norm = math.sqrt(sum(x * x for x in vector))
    if norm <= 1e-12:
        raise ValueError("Zero embedding")
    return [x / norm for x in vector]


def _local_embed(texts: list[str]) -> list[list[float]]:
    if os.getenv("E5_RUNTIME", "").lower()=="onnx":
        from .onnx_e5 import embed_onnx
        return embed_onnx(texts)
    global _LOCAL_MODEL
    if _LOCAL_MODEL is None:
        from sentence_transformers import SentenceTransformer
        _LOCAL_MODEL = SentenceTransformer(_MODEL_ID, device="cpu")
    vectors = _LOCAL_MODEL.encode(
        texts, batch_size=8, normalize_embeddings=True,
        convert_to_numpy=True, show_progress_bar=False
    )
    return [[float(v) for v in row] for row in vectors]


def embed(texts: list[str]) -> list[list[float]]:
    """Embedding service must return JSON {'vectors': [[...], ...]}."""
    url = os.getenv("E5_SERVICE_URL", "").strip()
    if url:
        import httpx
        if not url.startswith("https://") and not (
                os.getenv("APP_ENV") != "production" and
                url.startswith("http://127.0.0.1:")):
            raise ValueError("E5_SERVICE_URL must use HTTPS")
        token = os.getenv("E5_SERVICE_TOKEN", "")
        if not token:
            raise ValueError("E5_SERVICE_TOKEN is missing")
        with httpx.Client(timeout=httpx.Timeout(55, connect=5),
                          follow_redirects=False, trust_env=False) as client:
            response = client.post(
                url.rstrip("/") + "/embed",
                json={"texts": texts},
                headers={"Authorization": "Bearer " + token})
            response.raise_for_status()
            result = response.json()["vectors"]
    else:
        if os.getenv("E5_ENABLE_LOCAL") != "1":
            raise RuntimeError("E5 service is not configured")
        result = _local_embed(texts)
    if len(result) != len(texts):
        raise ValueError("Embedding count mismatch")
    normalized = [_normalized(row) for row in result]
    if len({len(v) for v in normalized}) != 1:
        raise ValueError("Embedding dimension mismatch")
    return normalized


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError("Vector dimension mismatch")
    return sum(x*y for x, y in zip(a, b))


def _balanced_shortlist(passages, reqs, lexical, budget):
    """Fair, deterministic candidate selection across ALL scanned passages.

    A popular criterion must not crowd out a rare criterion. Include known
    source rows, distributed coverage, then round-robin lexical candidates.
    """
    if len(passages)<=budget:
        return list(range(len(passages)))
    selected=[]; seen=set()
    def add(i):
        if i not in seen and len(selected)<budget:
            seen.add(i);selected.append(i)
    # The rule-based locator is independent evidence, not an E5 label.
    by_line={}
    for i,p in enumerate(passages):
        by_line.setdefault(p['line'],[]).append(i)
    for j,(check,_) in enumerate(reqs):
        loc=check.get('offer_locator') or {}
        line=loc.get('line',loc.get('value') if loc.get('kind')=='line' else None)
        hits=by_line.get(line,[])
        if hits:add(max(hits,key=lambda i:(lexical[j][i],-i)))
    for i in range(8):
        add(round(i*(len(passages)-1)/7))
    orders=[sorted(range(len(passages)),key=lambda i:(-row[i],i))[:max(32,budget)]
            for row in lexical]
    for rank in range(max((len(o) for o in orders),default=0)):
        for j,order in enumerate(orders):
            if rank<len(order) and lexical[j][order[rank]]>0:
                add(order[rank])
        if len(selected)>=budget:break
    # Zero-term/synonym-only queries still get some whole-document coverage.
    for i in range(budget):
        add(round(i*(len(passages)-1)/max(1,budget-1)))
    return sorted(selected)


def retrieve_e5(result: dict[str, Any], offers: list[tuple[str, str]],
                max_checks: int = 80, top_k: int = 3) -> dict[str, Any]:
    """Find candidate evidence; independently verify parameter identity later.

    Scan up to 5000 passages per proposal; bound encoder work on low-RAM
    hosts. Encode only one supplier at a time and cache shared query vectors.
    The deterministic compliance analyzer is NOT limited by this shortlist.
    """
    from .retrieval_baseline import bm25_scores
    hybrid=os.getenv("EVIDENCE_HYBRID","0")=="1"
    demo=os.getenv("E5_DEMO_MODE")=="1"
    batch_size=4 if os.getenv("E5_RUNTIME","").lower()=="onnx" else 32
    query_vectors={};results=[];coverage=[]
    for supplier in result.get("suppliers",[])[:10]:
        name=str(supplier.get("name",""))
        text=next((body for offer_name,body in offers if offer_name==name),"")
        all_passages=split_passages(text,max_passages=5001)
        truncated=len(all_passages)>5000
        all_passages=all_passages[:5000]
        checks=supplier.get("checks",[])
        reqs=[]
        for check in checks[:max_checks]:
            rq=(str(check.get("parameter") or "")+": "+
                str(check.get("criterion_text") or check.get("requirement_source") or ""))[:800]
            if rq.strip(" :"):reqs.append((check,rq))
        if not all_passages or not reqs:continue
        budget=max(32,min(256,4*len(reqs)+8)) if demo else 400
        lexical_full=bm25_scores([p["quote"] for p in all_passages],[rq for _,rq in reqs])
        indices=_balanced_shortlist(all_passages,reqs,lexical_full,budget)
        passages=[all_passages[i] for i in indices]
        lexical=[[row[i] for i in indices] for row in lexical_full]
        coverage.append({"supplier":name,"passages_scanned":len(all_passages),
                         "passages_indexed":len(passages),"checks_total":len(checks),
                         "checks_searched":len(reqs),"scan_truncated":truncated})
        del lexical_full,all_passages
        doc_texts=["passage: "+p["quote"] for p in passages]
        vectors=[]
        for i in range(0,len(doc_texts),batch_size):
            vectors.extend(embed(doc_texts[i:i+batch_size]))
        missing=list(dict.fromkeys("query: "+rq for _,rq in reqs
                                   if "query: "+rq not in query_vectors))
        for i in range(0,len(missing),batch_size):
            batch=missing[i:i+batch_size]
            query_vectors.update(zip(batch,embed(batch)))
        for j,(check,rq) in enumerate(reqs):
            q=query_vectors["query: "+rq]
            scores=[cosine(q,vector) for vector in vectors]
            dense_order=sorted(range(len(passages)),key=lambda i:(-scores[i],i))
            if hybrid:
                sparse_order=sorted(range(len(passages)),key=lambda i:(-lexical[j][i],i))
                fused=[0.0]*len(passages)
                for order in (dense_order,sparse_order):
                    for position,index in enumerate(order,1):
                        fused[index]+=1/(60+position)
                chosen=sorted(range(len(passages)),key=lambda i:(-fused[i],i))[:top_k]
            else:chosen=dense_order[:top_k]
            fragments=[]
            for index in chosen:
                p=passages[index]
                item={"quote":p["quote"],"line":p["line"],"location":p["location"],
                      "relevance_score":round(scores[index],4)}
                if hybrid:
                    item["rrf_score"]=round(fused[index],7)
                    item["bm25_score"]=round(lexical[j][index],4)
                fragments.append(item)
            results.append({"supplier":name,"section":check.get("section") or check.get("id"),
                            "parameter":str(check.get("parameter") or "")[:120],
                            "requirement_source":str(check.get("requirement_source") or "")[:300],
                            "fragments":fragments})
    if not results:return {"mode":"none","model":None,"results":[],"coverage":coverage,
                           "note":"Нет доступных фрагментов для поиска"}
    limited=any(c["scan_truncated"] or c["passages_indexed"]<c["passages_scanned"]
                or c["checks_searched"]<c["checks_total"] for c in coverage)
    return {"mode":"e5_bm25" if hybrid else "e5","model":_MODEL_ID,"results":results,
            "coverage":coverage,"limited":limited,
            "note":("E5+BM25 (RRF): поиск кандидатов, не оценка соответствия. "
                    "Предварительный отбор распределён по требованиям. "
                    "При ограничении семантического поиска основная проверка сканирует все извлечённые строки."
                    if hybrid else "Косинусное сходство — релевантность, не вероятность выполнения ТЗ.")}
