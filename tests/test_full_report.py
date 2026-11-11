"""Final report is source-backed, exhaustive and conservative."""
from app.full_report import build_full_report


def ck(parameter,status,mandatory=True,tz="ТЗ: 16 ГБ",kp="КП: 8 ГБ"):
    return {"parameter":parameter,"status":status,"mandatory":mandatory,
            "reason":"Проверка", "required":16,"actual":8,
            "unit":"ГБ","requirement_source":tz,"offer_source":kp,
            "requirement_locator":{"kind":"line","value":2},
            "offer_locator":{"kind":"line","value":5}}


def test_all_suppliers_and_evidence_are_preserved():
    result={"ranking":{"ranked":[
        {"supplier":"B","score":95,"components":{"price":{"label":"Цена","contribution":25,"effective_weight":25}}},
        {"supplier":"A","score":88,"components":{}}]},
        "suppliers":[
            {"name":"X","facts":[],"checks":[ck("ОЗУ","fail"),ck("Экран","pass")]},
            {"name":"A","facts":[{"key":"price","value":95000}],"checks":[ck("ОЗУ","pass")]},
            {"name":"C","facts":[],"checks":[ck("ОЗУ","unknown")]},
            {"name":"B","facts":[],"checks":[ck("ОЗУ","pass")]},
        ]}
    report=build_full_report(result)
    assert [s["supplier"] for s in report["suppliers"]]==["B","A","C","X"]
    assert [s["status"] for s in report["suppliers"]]==["eligible","eligible","review","rejected"]
    assert report["suppliers"][0]["score"]==95
    assert report["suppliers"][2]["score"] is None
    assert report["suppliers"][3]["score"] is None
    bad=report["suppliers"][3]["negatives"][0]
    assert bad["tz_quote"]=="ТЗ: 16 ГБ"
    assert bad["kp_quote"]=="КП: 8 ГБ"
    assert bad["tz_locator"]["value"]==2
    assert len(report["suppliers"][3]["positives"])==1
    assert [s["position"] for s in report["suppliers"]]==[1,2,3,4]


def test_no_accepted_suppliers_has_all_declined_or_reviewed():
    result={"ranking":{"ranked":[]},
        "suppliers":[
            {"name":"failed","checks":[ck("Цена","fail")]},
            {"name":"unknown","checks":[ck("Цена","unknown")]},
            {"name":"no_checks","checks":[]},
        ]}
    report=build_full_report(result)
    assert report["total"]==3
    assert report["eligible"]==0
    assert report["rejected"]==1
    assert report["review"]==2
    assert all(x["score"] is None for x in report["suppliers"])


def test_failed_optional_does_not_override_mandatory_eligibility():
    result={"ranking":{"ranked":[{"supplier":"A","score":65,"components":{}}]},
       "suppliers":[{"name":"A","checks":[ck("Память","pass",True),ck("Гарантия","fail",False)]}]}
    report=build_full_report(result)
    assert report["suppliers"][0]["status"]=="eligible"
    assert report["suppliers"][0]["score"]==65
    assert report["suppliers"][0]["failed"]==1
