"""Regression: numbered diesel-engine TZ must never collapse to two criteria."""
from app.analysis import analyze_documents
from app.ranking import build_ranking
from app.full_report import build_full_report

TZ="""Краткое ТЗ на закупку ДВС
2.1. Тип: дизельный, 4-тактный, рядный или V-образный.
2.2. Модель и маркировка: соответствие штатному ДВС ТС (указать модель и номер).
2.3. Мощность: не менее 150 кВт (204 л.с.).
2.4. Рабочий объём: 6,0 л с допуском ±5%.
2.5. Число цилиндров: 6.
2.6. Экологический класс: не ниже Евро-4.
2.7. Система охлаждения: жидкостная.
2.8. Комплектность: в сборе — блок, ГБЦ, ТНВД, турбокомпрессор, генератор, стартер, форсунки, жгуты, навесное оборудование.
2.9. Состояние: новый или восстановленный (капремонт) с подтверждением.
2.10. Ресурс: не менее 10 000 моточасов.
2.11. Гарантия: не менее 12 месяцев или 10 000 моточасов.
3.1. Срок поставки: не более 30 календарных дней с даты подписания договора.
3.2. Условия поставки: до склада Заказчика, разгрузка силами Поставщика.
3.3. Документы: паспорт или формуляр ДВС, сертификат соответствия, гарантийный талон, товарная накладная, счёт-фактура или УПД.
3.4. Упаковка: транспортная тара, обеспечивающая сохранность при перевозке.
4.1. Опыт поставок аналогичной продукции: не менее 3 лет.
4.2. Наличие сервисной поддержки или возможности гарантийного ремонта.
4.3. Отсутствие в реестре недобросовестных поставщиков."""
KP="""Технические характеристики:
2.1. Тип: дизельный, 4-тактный, рядный, жидкостного охлаждения.
2.2. Модель: ЯМЗ-536 (заявлено соответствие штатному ДВС, номер 536-1234567).
2.3. Мощность: 165 кВт (224 л.с.).
2.4. Рабочий объём: 6,0 л.
2.5. Число цилиндров: 6.
2.6. Экологический класс: Евро-4.
2.7. Комплектность: в сборе — блок цилиндров, ГБЦ, ТНВД, турбокомпрессор, форсунки, генератор, стартер, жгуты проводов, навесное оборудование.
2.8. Состояние: новый (заводская сборка).
2.9. Ресурс: не менее 12 000 моточасов.
2.10. Гарантия: 24 месяца.
3.1. Срок поставки: 20 календарных дней.
3.2. Доставка до склада Заказчика, разгрузка силами Поставщика.
3.3. Упаковка: транспортная тара.
Комплект документов: паспорт-формуляр ДВС, сертификат соответствия, гарантийный талон, УПД, счёт-фактура.
Цена 1250000 руб.
Сведения о Поставщике: опыт поставок ДВС — 7 лет, сервисный центр есть, гарантийный ремонт собственными силами; в реестре недобросовестных поставщиков отсутствует."""

def test_numbered_tz_exposes_all_18_criteria_and_uncertainties():
    name="длинное_коммерческое_предложение_" + "П"*155 + ".txt"
    report=analyze_documents(TZ,[(name,KP)])
    assert report["engine"]=="numbered-criteria-v1"
    assert len(report["requirements"])==18
    offer=report["suppliers"][0]
    assert offer["name"]==name
    assert len(offer["checks"])==18
    statuses={c["id"]:c["status"] for c in offer["checks"]}
    assert statuses["2.3"]=="pass" # 165 >= 150 kW
    assert statuses["2.4"]=="pass" # within +/-5%
    assert statuses["2.5"]=="pass" # six cylinders; not the clause number 2.5
    assert statuses["3.1"]=="pass" # 20 <= 30 days
    assert statuses["2.2"]=="unknown" # independent vehicle compatibility required
    assert statuses["3.3"]=="unknown" # missing separate goods invoice; UPD review
    assert statuses["4.3"]=="unknown" # registry not independently verified
    assert (offer["passed"],offer["failed"],offer["unknown"])==(15,0,3)
    assert all(c["requirement_source"] and c["requirement_locator"] for c in offer["checks"])
    assert all(c["offer_locator"] for c in offer["checks"] if c["offer_source"])
    rank=build_ranking(report)
    assert rank["recommended"] is None
    report["ranking"]=rank
    full=build_full_report(report)
    assert full["total"]==1 and full["review"]==1 and full["eligible"]==0
    assert full["suppliers"][0]["mandatory_total"]==18

def test_numbered_tz_does_not_mistake_a_small_engine_for_compliance():
    modified=KP.replace("Мощность: 165 кВт","Мощность: 110 кВт")
    report=analyze_documents(TZ,[("inferior.txt",modified)])
    check=next(c for c in report["suppliers"][0]["checks"] if c["id"]=="2.3")
    assert check["status"]=="fail"
    assert check["actual"]==110
    assert report["suppliers"][0]["mandatory_failed"]==1

def test_missing_offer_field_is_unknown_not_pass():
    modified=KP.replace("2.10. Гарантия: 24 месяца.","")
    report=analyze_documents(TZ,[("missing_warranty.txt",modified)])
    check=next(c for c in report["suppliers"][0]["checks"] if c["id"]=="2.11")
    assert check["status"]=="unknown"
    assert check["offer_source"] is None

def test_unnumbered_tz_keeps_original_rules():
    report=analyze_documents("Мощность не менее 5 кВт", [("offer.txt","Мощность 6 кВт")])
    assert report["engine"]!="numbered-criteria-v1"
