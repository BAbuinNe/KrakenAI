"""Production-equivalent E5+BM25 smoke, without any external API.

Runs in the Docker build using the exact quantized ONNX weights that ship
with the free production service.
"""
import os
from .embedding_search import retrieve_e5

def main():
    os.environ["E5_DEMO_MODE"]="1"
    os.environ["EVIDENCE_HYBRID"]="1"
    os.environ["E5_ENABLE_LOCAL"]="1"
    os.environ["E5_RUNTIME"]="onnx"
    checks=[{"parameter":"Оперативная память",
             "requirement_source":"ОЗУ не менее 16 ГБ",
             "mandatory":True,"status":"fail"}]
    original_status=checks[0]["status"]
    report={"suppliers":[{"name":"offer.txt","checks":checks}]}
    offers=[("offer.txt","Возможность сотрудничества\nОперативная память RAM 8 ГБ DDR4\nНакопитель SSD 512 ГБ")]
    evidence=retrieve_e5(report,offers,max_checks=3,top_k=3)
    assert evidence["mode"]=="e5_bm25",evidence
    matches=evidence["results"][0]["fragments"]
    assert len(matches)==3
    assert any("RAM 8 ГБ" in m["quote"] for m in matches),matches
    assert all(isinstance(m["rrf_score"],float) and isinstance(m["relevance_score"],float)
               and m["line"]>=1 for m in matches)
    assert report["suppliers"][0]["checks"][0]["status"]==original_status
    print("KRAKEN E5+BM25 ONNX REAL-INFERENCE SMOKE OK",flush=True)

if __name__=="__main__":
    main()
