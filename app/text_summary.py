"""Safe extractive KP previews inspired by Szhatie_Kp.py.

This is NOT a replacement for the document used by compliance checks.
It NEVER deletes content from the source, changes numeric comparisons,
or appends context-free facts. Used only to display an optional preview.
"""
from __future__ import annotations
import re
from typing import Any

_SPACES=re.compile(r"[ \t\u00a0]+")
_WORDS=re.compile(r"[a-zа-яё0-9]{3,}",re.I)
_FACT=re.compile(r"\d+[\s.,\d]*(?:₽|руб\w*|гб|тб|кг|мм|шт\.?|дн\w*|мес\w*|%|квт|вт|год\w*|лет)?",re.I)
_KEY=re.compile(r"цена|стоимост|итого|ндс|гаранти|поставк|оплат|характерист|модель|количеств|срок|соответств|услови",re.I)

def preview(kp_text:str,tz_text:str,max_chars:int=3600)->dict[str,Any]:
    """Return direct verbatim source lines selected with TZ + BM25-like overlap.

    Important: preview does not assert full coverage. Original text is retained
    and analyzed separately. Avoid removing duplicated lines or labels.
    """
    original=len(kp_text)
    terms=set(_WORDS.findall(tz_text.casefold()))
    candidates=[]
    for n,raw in enumerate(kp_text.splitlines(),1):
        line=_SPACES.sub(" ",raw.strip())
        if len(line)<3:continue
        matches=len(terms & set(_WORDS.findall(line.casefold())))
        related=matches/max(1,len(terms))
        priority=3.0*related + (0.45 if _KEY.search(line) else 0) + (0.15 if _FACT.search(line) else 0)
        # Never claim semantic equivalence from lexical preview scores.
        candidates.append((priority,n,line))
    if not candidates:
        return {"source_chars":original,"preview_chars":0,
                "lines_selected":0,"lines_total":0,"excerpts":[],
                "complete":not bool(kp_text.strip())}
    ranked=sorted(candidates,key=lambda x:(-x[0],x[1]))
    chosen=[]
    remaining=max_chars
    for score,line_no,line in ranked:
        # Do not cut quotes halfway: preserve complete source lines only.
        if len(line)+1>remaining:continue
        chosen.append((line_no,line))
        remaining-=len(line)+1
        if remaining<24:break
    chosen.sort(key=lambda t:t[0])
    excerpts=[{"line":n,"text":value} for n,value in chosen]
    return {"source_chars":original,
            "preview_chars":sum(len(x["text"]) for x in excerpts),
            "lines_selected":len(excerpts),"lines_total":len(candidates),
            "excerpts":excerpts[:24],
            "complete":len(excerpts)==len(candidates),
            "method":"Извлечение строк по совпадениям с ТЗ и ключевым терминам; исходные файлы не изменяются"}
