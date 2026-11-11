"""Safety tests for TZ-guided previews: never mutate or replace the original."""
from app.text_summary import preview

TZ = "Память не менее 16 ГБ. Цена не более 250000 рублей. Гарантия 24 месяца."

def test_preview_retains_original_and_source_lines():
    kp = ("ООО Поставщик\n" +
          "Наша история и преимущества.\n"*10 +
          "Оперативная память 32 ГБ\n"+
          "Цена 238 000 рублей\n"+
          "Гарантия 24 месяца\n")
    source=kp[:]
    result=preview(kp,TZ,max_chars=400)
    assert kp==source
    assert result["source_chars"]==len(source)
    assert all(isinstance(e["line"],int) and e["text"] in source
               for e in result["excerpts"])
    assert any("Цена 238 000 рублей" in e["text"] for e in result["excerpts"])

def test_duplicate_price_lines_not_erased():
    kp="Цена 200 000 рублей\nЦена 200 000 рублей\nГарантия 24 месяца"
    result=preview(kp,TZ,max_chars=1500)
    assert sum(e["text"]=="Цена 200 000 рублей" for e in result["excerpts"])==2
    assert result["complete"] is True

def test_very_long_line_never_gets_cut_mid_fact():
    kp="Стоимость "+("описание " * 600)+" 999999 руб"
    result=preview(kp,TZ,max_chars=350)
    assert result["preview_chars"]<=350
    assert result["complete"] is False
    assert kp.endswith("999999 руб")
    assert all(e["text"] in kp for e in result["excerpts"])
