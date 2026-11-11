"""Reproducible, isolated TZ -> KP passage retrieval baseline.

CLI (inside Kraken Docker image):
  python -m app.retrieval_baseline --tz samples/tz.txt --kp samples/offer1.txt samples/offer2.txt --model e5 --top-k 5

Modes: e5 (local ONNX), tfidf (NumPy), bm25 (classic lexical score),
       minilm (optional sentence-transformers on a suitable machine).
E5/MiniLM/TF-IDF are ranked by MINIMUM COSINE DISTANCE. BM25 is included
as a non-cosine lexical comparison and labelled honestly.
Nothing here makes a PASS/FAIL decision about procurement requirements.
"""
from __future__ import annotations
import argparse
import json
import math
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

_WORD=re.compile(r"[a-zа-яё0-9]+",re.I)


def tokens(value:str)->list[str]:
    return _WORD.findall(value.casefold())


def split_text(text:str,name:str,max_chars:int=720,overlap:int=80)->list[dict[str,Any]]:
    """Preserve file, original line, and verbatim excerpt; split long lines."""
    result=[]
    if overlap>=max_chars or max_chars<100:
        raise ValueError("Expected 100<=overlap<max_chars")
    for line_no,raw in enumerate(text.splitlines(),1):
        raw=raw.strip()
        if not raw:continue
        start=0
        while start<len(raw):
            piece=raw[start:start+max_chars]
            if piece.strip():
                result.append({"id":f"{name}:{line_no}:{start}","document":name,
                               "line":line_no,"offset":start,"text":piece})
            if start+max_chars>=len(raw):break
            start+=max_chars-overlap
    return result


def tfidf_vectors(docs:list[str],queries:list[str])->tuple[list[list[float]],list[list[float]]]:
    """Same IDF vocabulary for all passages and queries. No fitted test labels."""
    from numpy import zeros, log, log1p, linalg
    text=[tokens(s) for s in docs+queries]
    vocab={term:i for i,term in enumerate(sorted(set(w for row in text for w in row)))}
    df=Counter(w for row in text[:len(docs)] for w in set(row))
    # Document-only training prevents queries from influencing corpus IDF.
    idf={w:math.log((1+len(docs))/(1+df.get(w,0)))+1 for w in vocab}
    vectors=[]
    for row in text:
        vector=zeros(len(vocab),dtype="float32")
        for word,count in Counter(row).items():
            vector[vocab[word]]=(1+math.log(count))*idf[word]
        norm=linalg.norm(vector)
        if norm:vector/=norm
        vectors.append(vector.tolist())
    return vectors[:len(docs)],vectors[len(docs):]


def dense_vectors(docs:list[str],queries:list[str],model:str)->tuple[list[list[float]],list[list[float]]]:
    if model=="tfidf":return tfidf_vectors(docs,queries)
    if model=="e5":
        from .onnx_e5 import embed_onnx
        return (embed_onnx(["passage: "+s for s in docs]),
                embed_onnx(["query: "+s for s in queries]))
    if model=="minilm":
        # Optional: runs on developer PC, not bundled into 512MB Render image.
        from sentence_transformers import SentenceTransformer
        encoder=SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        return (encoder.encode(docs,batch_size=8,normalize_embeddings=True).tolist(),
                encoder.encode(queries,batch_size=8,normalize_embeddings=True).tolist())
    raise ValueError("Unknown model "+model)


def bm25_scores(docs:list[str],queries:list[str])->list[list[float]]:
    doc_terms=[tokens(d) for d in docs]
    counts=[Counter(row) for row in doc_terms]
    N=len(docs)
    avg=sum(map(len,doc_terms))/max(1,N)
    df=Counter(w for row in doc_terms for w in set(row))
    idf={w:math.log(1+(N-n+.5)/(n+.5)) for w,n in df.items()}
    output=[]
    for query in queries:
        row=[]
        for i,tf in enumerate(counts):
            score=0.
            for w in set(tokens(query)):
                f=tf.get(w,0)
                if f:
                    denominator=f+1.5*(.25+.75*len(doc_terms[i])/max(avg,1))
                    score+=idf.get(w,0)*f*2.5/denominator
            row.append(score)
        output.append(row)
    return output


def search(queries:list[str],passages:list[dict[str,Any]],model:str="e5",
           top_k:int=5)->dict[str,Any]:
    if not passages:raise ValueError("Empty corpus")
    if not queries:raise ValueError("Empty queries")
    if top_k<1:raise ValueError("top_k must be positive")
    docs=[str(p["text"]) for p in passages]
    start=time.perf_counter()
    if model=="bm25":
        matrix=bm25_scores(docs,queries)
        results=[sorted(enumerate(row),key=lambda x:(-x[1],x[0]))[:top_k] for row in matrix]
    else:
        documents,questions=dense_vectors(docs,queries,model)
        # Cosine distance = 1 - normalized dot product.
        if len(documents)!=len(docs) or len(questions)!=len(queries):
            raise ValueError("Embedding count mismatch")
        def normalize(row):
            norm=math.sqrt(sum(float(v)**2 for v in row))
            if norm==0:return [0.]*len(row)
            return [float(v)/norm for v in row]
        documents=[normalize(x) for x in documents]
        questions=[normalize(x) for x in questions]
        results=[]
        for q in questions:
            row=[(i,1-sum(a*b for a,b in zip(q,d))) for i,d in enumerate(documents)]
            results.append(sorted(row,key=lambda x:(x[1],x[0]))[:top_k])
    elapsed=time.perf_counter()-start
    output=[]
    for query,ranked in zip(queries,results):
        matches=[]
        for i,metric in ranked:
            match={k:passages[i][k] for k in ("id","document","line","offset","text")}
            if model=="bm25":
                match["bm25_score"]=round(float(metric),6)
            else:
                match["cosine_distance"]=round(float(metric),6)
                match["cosine_similarity"]=round(1-float(metric),6)
            matches.append(match)
        output.append({"query":query,"top":matches})
    return {"model":model,"metric":"BM25 descending" if model=="bm25" else
            "cosine_distance ascending","elapsed_seconds":round(elapsed,4),
            "passages":len(passages),"queries":output}


def cli():
    parser=argparse.ArgumentParser(description="Rank KP passages by minimum cosine distance")
    parser.add_argument("--tz",type=Path,required=True,help="UTF-8 technical specification TXT")
    parser.add_argument("--kp",type=Path,nargs="+",required=True,help="UTF-8 offer TXT files")
    parser.add_argument("--model",choices=["e5","tfidf","bm25","minilm"],default="e5")
    parser.add_argument("--top-k",type=int,default=5)
    parser.add_argument("--query",action="append",help="Single requirement; repeatable. Otherwise nonempty TZ lines are queries.")
    parser.add_argument("--output",type=Path,help="Optional JSON output file")
    args=parser.parse_args()
    tz=args.tz.read_text(encoding="utf-8-sig")
    queries=args.query or [x.strip() for x in tz.splitlines() if len(x.strip())>=8]
    corpus=[]
    for path in args.kp:
        corpus.extend(split_text(path.read_text(encoding="utf-8-sig"),path.name))
    data=search(queries,corpus,args.model,args.top_k)
    rendered=json.dumps(data,ensure_ascii=False,indent=2)
    if args.output:args.output.write_text(rendered,encoding="utf-8")
    print(rendered)


if __name__=="__main__":
    cli()
