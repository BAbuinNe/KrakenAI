"""Unit tests for chunking, cosine similarity and private E5 retrieval."""
import pytest
from app import embedding_search


def test_chunking_keeps_source_line():
    document="Страница 2:\n"+"Цена "+("1200 " * 400)
    passages=embedding_search.split_passages(document,max_chars=120,overlap=20)
    assert len(passages)>1
    assert all(p["line"]==2 and p["location"]=="Страница 2" for p in passages)
    assert passages[0]["quote"].startswith("Цена")


def test_cosine_unit_norm():
    a=embedding_search._normalized([3,4])
    b=embedding_search._normalized([0,5])
    assert embedding_search.cosine(a,b)==pytest.approx(.8)


def test_retrieve_e5_uses_prefixes_and_original_source(monkeypatch):
    seen=[]
    def fake_embed(texts):
        seen.extend(texts)
        def vec(text):
            if "RAM" in text or "ОЗУ" in text or "Память" in text:
                return [1.0,0.0]
            return [0.0,1.0]
        return [vec(x) for x in texts]
    monkeypatch.setattr(embedding_search,"embed",fake_embed)
    result={"suppliers":[{"name":"one.txt","checks":[{"parameter":"Память",
        "requirement_source":"ОЗУ не менее 16 ГБ","status":"unknown","mandatory":True}]}]}
    payload=embedding_search.retrieve_e5(result,[("one.txt","SSD 256 ГБ\nRAM 16 ГБ")])
    assert payload["mode"]=="e5"
    assert payload["results"][0]["fragments"][0]["quote"]=="RAM 16 ГБ"
    assert any(t.startswith("query: ") for t in seen)
    assert any(t.startswith("passage: ") for t in seen)


def test_missing_service_does_not_fabricate_embeddings(monkeypatch):
    monkeypatch.delenv("E5_SERVICE_URL",raising=False)
    monkeypatch.delenv("E5_ENABLE_LOCAL",raising=False)
    with pytest.raises(RuntimeError):
        embedding_search.embed(["query: test"])
