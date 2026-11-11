"""Evidence-backed full supplier ordering for display.

Do NOT treat an excluded/unknown supplier as an eligible candidate or turn
heuristic pass counts into quality scores. Detailed rows cite original TZ/KP.
"""
from __future__ import annotations
from typing import Any


def _status(s:dict[str,Any])->str:
    mandatory=[c for c in s.get("checks",[]) if c.get("mandatory",True)]
    if any(c.get("status")=="fail" for c in mandatory):return "rejected"
    if not mandatory or any(c.get("status")!="pass" for c in mandatory):return "review"
    return "eligible"


def _source(check:dict[str,Any],key:str)->str|None:
    v=check.get(key)
    return str(v).strip()[:420] if v is not None and str(v).strip() else None


def _checked_item(check:dict[str,Any])->dict[str,Any]:
    return {
        "parameter":str(check.get("parameter") or "Характеристика")[:130],
        "mandatory":bool(check.get("mandatory",True)),
        "status":str(check.get("status") or "unknown"),
        "required":check.get("required"),
        "actual":check.get("actual"),
        "unit":str(check.get("unit") or "")[:30],
        "reason":str(check.get("reason") or "")[:250],
        "tz_quote":_source(check,"requirement_source"),
        "kp_quote":_source(check,"offer_source"),
        "tz_locator":check.get("requirement_locator"),
        "kp_locator":check.get("offer_locator"),
    }


def build_full_report(result:dict[str,Any])->dict[str,Any]:
    rank=result.get("ranking") or {}
    suppliers=result.get("suppliers") or []
    score_map={r.get("supplier"):r for r in rank.get("ranked",[])}
    qualified_order={r.get("supplier"):i for i,r in enumerate(rank.get("ranked",[]))}
    entries=[]
    for s in suppliers:
        status=_status(s)
        checks=[_checked_item(c) for c in s.get("checks",[])]
        good=[c for c in checks if c["status"]=="pass"]
        bad=[c for c in checks if c["status"]=="fail"]
        unknown=[c for c in checks if c["status"]=="unknown"]
        mandatory=[c for c in checks if c["mandatory"]]
        passing_mandatory=sum(c["status"]=="pass" for c in mandatory)
        price=next((f.get("value") for f in s.get("facts",[])
                    if f.get("key")=="price" and isinstance(f.get("value"),(int,float))
                    and not isinstance(f.get("value"),bool)),None)
        if price is None and isinstance(s.get("price"),(float,int)):
            price=s["price"]
        ranked=score_map.get(s.get("name"))
        # A numeric score is only valid for fully eligible suppliers with an
        # actual calculated rank. Others are shown "not rated".
        score=ranked.get("score") if status=="eligible" and ranked else None
        entries.append({
            "supplier":s.get("name","КП"),"status":status,
            "label":{"eligible":"Допущен","review":"Требует уточнения","rejected":"Не допущен"}[status],
            "score":score,
            "price_rub":price,
            "components":ranked.get("components",{}) if ranked and status=="eligible" else {},
            "mandatory_total":len(mandatory),
            "mandatory_passed":passing_mandatory,
            "passed":len(good),"failed":len(bad),"unknown":len(unknown),
            "positives":good,"negatives":bad,"uncertain":unknown,
            "checks":checks,
            "rank_index":qualified_order.get(s.get("name")),
            "why_not":("Нарушено обязательное требование ТЗ" if status=="rejected"
                       else "Недостаточно данных для подтверждения всех обязательных требований"
                       if status=="review" else None),
        })
    # Strict ordering: fully compliant, incomplete, mandatory violation.
    # Among inadmissible/incomplete suppliers, counts are a *review priority*
    # rather than procurement ranking. Never recommend these suppliers.
    ordering={"eligible":0,"review":1,"rejected":2}
    entries.sort(key=lambda x:(
        ordering[x["status"]],
        x["rank_index"] if x["status"]=="eligible" and x["rank_index"] is not None else
        -(x["mandatory_passed"]/x["mandatory_total"] if x["mandatory_total"] else 0),
        x["failed"] if x["status"]=="rejected" else x["unknown"],
        str(x["supplier"]).casefold()))
    for i,entry in enumerate(entries,1):
        entry["position"]=i
        entry.pop("rank_index",None)
    return {"suppliers":entries,"total":len(entries),
            "eligible":sum(x["status"]=="eligible" for x in entries),
            "review":sum(x["status"]=="review" for x in entries),
            "rejected":sum(x["status"]=="rejected" for x in entries),
            "note":("Итоговый порядок: допущенные по расчётному баллу; затем требующие уточнения; "
                    "последними — нарушившие обязательные условия. Позиции недопущенных — "
                    "приоритет проверки, не рекомендация к покупке. Все выводы "
                    "основаны только на извлечённых требованиях и документах.")}
