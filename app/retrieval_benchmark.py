"""Benchmark reproducible retrieval against annotated passage relevance.

No training split, no gold in scoring, no vendor eligibility claims.
Run:
 python -m app.retrieval_benchmark --dataset benchmarks/ru_procurement_synthetic_v1.json --models tfidf bm25 e5
 Optional MiniLM on developer PC with sentence-transformers installed.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
from .retrieval_baseline import search


def evaluate(dataset:dict,model:str,top_k:int=5)->dict:
    paragraphs=[{"id":p["id"],"document":"synthetic-KP.txt","line":i+1,
                 "offset":0,"text":p["text"]} for i,p in enumerate(dataset["passages"])]
    queries=[p["query"] for p in dataset["queries"]]
    output=search(queries,paragraphs,model,top_k)
    metrics={"recall@1":0.0,"recall@3":0.0,"recall@5":0.0,
             "mrr@5":0.0,"ndcg@5":0.0,"hit@1":0.0}
    per_query=[]
    for case,found in zip(dataset["queries"],output["queries"]):
        actual=[row["id"] for row in found["top"]]
        gold=set(case["relevant"])
        if not gold:raise ValueError("Every query needs a nonempty gold set")
        for k in (1,3,5):
            metrics[f"recall@{k}"]+=len(gold.intersection(actual[:k]))/len(gold)
        metrics["hit@1"]+=float(actual[0] in gold) if actual else 0.0
        match_rank=next((i+1 for i,id in enumerate(actual[:5]) if id in gold),None)
        metrics["mrr@5"]+=1/match_rank if match_rank else 0.0
        dcg=sum((1 if x in gold else 0)/math.log2(i+2) for i,x in enumerate(actual[:5]))
        ideal=sum(1/math.log2(i+2) for i in range(min(5,len(gold))))
        metrics["ndcg@5"]+=dcg/ideal if ideal else 0.0
        per_query.append({"id":case["id"],"query":case["query"],
                          "expected":sorted(gold),"retrieved":actual,
                          "first_relevant_rank":match_rank,
                          "first_distance":(found["top"][0].get("cosine_distance")
                                            if found["top"] and model!="bm25" else None)})
    count=len(queries)
    return {"model":model,"queries":count,"passages":len(paragraphs),
            "metrics":{k:round(v/count,4) for k,v in metrics.items()},
            "seconds":output["elapsed_seconds"],"per_query":per_query}


def run(models:list[str],dataset_path:Path)->dict:
    dataset=json.loads(dataset_path.read_text(encoding="utf-8"))
    result={"dataset":str(dataset_path),
            "description":dataset.get("description"),
            "model_results":[],"failures":[]}
    for model in models:
        try:
            result["model_results"].append(evaluate(dataset,model))
        except (ImportError,OSError,RuntimeError,ValueError) as exc:
            result["failures"].append({"model":model,"reason":str(exc)[:250]})
    return result


def cli():
    p=argparse.ArgumentParser()
    p.add_argument("--dataset",type=Path,default=Path("benchmarks/ru_procurement_synthetic_v1.json"))
    p.add_argument("--models",nargs="+",choices=["tfidf","bm25","e5","minilm"],
                   default=["tfidf","bm25","e5"])
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    results=run(args.models,args.dataset)
    output=json.dumps(results,ensure_ascii=False,indent=2)
    if args.output:args.output.write_text(output,encoding="utf-8")
    print(output)


if __name__=="__main__":
    cli()
