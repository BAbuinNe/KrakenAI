"""Validate ranking direction, evidence integrity, and benchmark metrics."""
from app.retrieval_baseline import search, split_text
from app.retrieval_benchmark import evaluate


def test_tfidf_orders_by_minimum_cosine_distance():
    paragraphs=[
        {"id":"one","document":"a.txt","line":1,"offset":0,"text":"поставка мониторов 4K"},
        {"id":"two","document":"b.txt","line":1,"offset":0,"text":"гарантия на аккумулятор 12 месяцев"},
        {"id":"three","document":"c.txt","line":2,"offset":0,"text":"поставка мониторов Full HD"},
    ]
    out=search(["поставка мониторов 4K"],paragraphs,model="tfidf",top_k=3)
    matched=out["queries"][0]["top"]
    assert matched[0]["id"]=="one"
    assert matched[0]["cosine_distance"]<=matched[1]["cosine_distance"]<=matched[2]["cosine_distance"]
    assert all(row["document"] and row["line"] for row in matched)


def test_chunking_preserves_offsets_without_losing_source():
    text="A"*1500+"\nЦена 10000 руб."
    chunks=split_text(text,"offer.txt",max_chars=300,overlap=50)
    assert len(chunks)>4
    assert any(item["line"]==2 and "Цена" in item["text"] for item in chunks)
    for item in chunks:
        start=item["offset"]
        original=text.splitlines()[item["line"]-1]
        assert original[start:start+len(item["text"])]==item["text"]


def test_benchmark_relevant_at_top():
    dataset={"passages":[{"id":"good","text":"В комплекте есть HDMI"},
                          {"id":"bad","text":"Цена 10000 руб."}],
             "queries":[{"id":"q","query":"HDMI","relevant":["good"]}]}
    result=evaluate(dataset,"tfidf")
    assert result["metrics"]["recall@1"]==1
    assert result["metrics"]["mrr@5"]==1
    assert result["metrics"]["ndcg@5"]==1

def test_hybrid_rrf_is_deterministic_and_has_no_fake_cosine_score(monkeypatch):
    import app.retrieval_baseline as baseline
    paragraphs=[
        {"id":"a","document":"a.txt","line":1,"offset":0,"text":"ОЗУ 16 ГБ"},
        {"id":"b","document":"b.txt","line":1,"offset":0,"text":"RAM 8 GB"},
        {"id":"c","document":"c.txt","line":1,"offset":0,"text":"SSD накопитель"},
    ]
    monkeypatch.setattr(baseline,"dense_vectors",lambda docs,queries,model:
        ([[1.,0.],[0.8,0.6],[0.,1.]],[[1.,0.]]))
    one=baseline.search(["ОЗУ 16 ГБ"],paragraphs,model="hybrid",top_k=3)
    two=baseline.search(["ОЗУ 16 ГБ"],paragraphs,model="hybrid",top_k=3)
    assert [r["id"] for r in one["queries"][0]["top"]]==[r["id"] for r in two["queries"][0]["top"]]
    assert one["metric"]=="RRF fused-rank descending"
    assert all("rrf_score" in r and "cosine_distance" not in r for r in one["queries"][0]["top"])
