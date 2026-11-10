"""Bounded source retrieval for a session-owned procurement analysis.

This is lexical retrieval, NOT semantic search. All excerpts are untrusted.
Only parsed text in the requesting session may be passed to Gemini.
"""
from __future__ import annotations
import re
from typing import Any

WORDS=re.compile(r"[a-zа-яё0-9]{3,}",re.I)
STOP={"какой","какие","какая","какого","после","этого","почему","нужно",
      "можно","покажи","сравни","этот","этого","который","поставщик",
      "поставщика","поставщиков","пожалуйста","расскажи","требования",
      "коммерческое","предложение","документ","документы"}

def tokens(value:str)->set[str]:
    return {w for w in WORDS.findall(value.casefold()) if w not in STOP}

def _fragments(document:dict[str,Any]) -> list[dict[str,str]]:
    name=str(document.get("name",""))[:150]
    role=document.get("role","proposal")
    text=str(document.get("text",""))[:15000]
    current="не указано"
    out=[]
    for index,line in enumerate(text.splitlines()):
        value=line.strip()
        if not value:continue
        page=re.match(r"^Страница\s+(\d+):\s*$",value,re.I)
        if page:
            current="стр. "+page.group(1)
            continue
        if value.startswith("Лист: "):
            current="лист "+value[6:].strip()[:60]
            continue
        for offset in range(0,len(value),650):
            snippet=value[offset:offset+650]
            if len(snippet)<4:continue
            out.append({"document":name,"role":role,"location":current,
                        "line":str(index+1),"quote":snippet})
            if len(out)>=120: return out
    return out

def retrieve_evidence(documents:list[dict[str,Any]], question:str,
                      limit:int=10)->list[dict[str,str]]:
    """Prefer exact text overlap and one source per document for broad queries."""
    if not documents:return []
    wanted=tokens(question)
    selected=[]
    for di,document in enumerate(documents[:11]):
        excerpts=_fragments(document)
        if not excerpts:continue
        name_tokens=tokens(str(document.get("name","")))
        relevance=len(wanted & name_tokens)
        scored=[]
        for fi,excerpt in enumerate(excerpts):
            overlap=len(wanted & tokens(excerpt["quote"]))
            score=3*overlap+2*relevance
            scored.append((score,-fi,excerpt))
        scored.sort(key=lambda x:(-x[0],-x[1]))
        for rank,(score,_,excerpt) in enumerate(scored[:3]):
            selected.append((score, -rank, -di,excerpt))
    selected.sort(key=lambda row:(-row[0],-row[1],-row[2]))
    chosen=[]
    counts={}
    for score,_,_,excerpt in selected:
        name=excerpt["document"]
        if counts.get(name,0)>=2:continue
        chosen.append(excerpt)
        counts[name]=counts.get(name,0)+1
        if len(chosen)>=limit:break
    return chosen
