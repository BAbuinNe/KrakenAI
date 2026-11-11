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


def test_hybrid_e5_bm25_keeps_cosine_and_rrf_separate(monkeypatch):
    monkeypatch.setenv("EVIDENCE_HYBRID","1")
    def fake_embed(texts):
        return [[1.0,0.0] if "RAM" in text or "ОЗУ" in text or "Память" in text
                else [0.0,1.0] for text in texts]
    monkeypatch.setattr(embedding_search,"embed",fake_embed)
    result={"suppliers":[{"name":"offer.txt","checks":[{
        "parameter":"Память","requirement_source":"ОЗУ 16 ГБ","status":"pass",
        "mandatory":True}]}]}
    data=embedding_search.retrieve_e5(result,[("offer.txt","SSD 512 ГБ\nRAM 16 ГБ")])
    assert data["mode"]=="e5_bm25"
    fragments=data["results"][0]["fragments"]
    assert fragments and "rrf_score" in fragments[0] and "relevance_score" in fragments[0]
    assert fragments[0]["quote"] in ("RAM 16 ГБ","SSD 512 ГБ")


def test_demo_prefilter_limits_embedding_work_without_losing_sources(monkeypatch):
    monkeypatch.setenv("E5_DEMO_MODE","1")
    monkeypatch.setenv("EVIDENCE_HYBRID","1")
    observed=[]
    def fake_embed(texts):
        observed.extend(texts)
        return [[1.0,0.0] if "RAM" in text or "ОЗУ" in text
                else [0.0,1.0] for text in texts]
    monkeypatch.setattr(embedding_search,"embed",fake_embed)
    lines=["Нерелевантная строка о сотрудничестве номер "+str(i)
           for i in range(100)]
    lines.insert(65,"RAM 16 ГБ DDR5")
    req={"suppliers":[{"name":"offer.txt","checks":[{
        "parameter":"ОЗУ","requirement_source":"RAM не менее 16 ГБ",
        "status":"pass","mandatory":True}]}]}
    res=embedding_search.retrieve_e5(req,[("offer.txt","\n".join(lines))])
    assert res["mode"]=="e5_bm25"
    assert len([x for x in observed if x.startswith("passage:")])<=32
    assert len([x for x in observed if x.startswith("query:")])==1
    assert res["results"][0]["fragments"][0]["quote"]=="RAM 16 ГБ DDR5"
    assert res["results"][0]["fragments"][0]["line"]==66
