"""Evaluate explicit gold labels, never infer the gold from the analyzer.
Run: python -m app.workspace_benchmark --models bm25 e5 hybrid
Optional local CrossEncoder: --models cross_encoder --cross-model /path/to/model
"""
import argparse
import json
import math
from pathlib import Path
from collections import Counter
from .analysis import analyze_documents, _items
from .ranking import build_ranking
from .retrieval_baseline import search, split_text

DATA=Path(__file__).resolve().parent.parent/'benchmarks/workspace_synthetic_50.json'
CLASSES=('pass','fail','unknown')

def f1(gold,pred,label):
    tp=sum(a==b==label for a,b in zip(gold,pred))
    fp=sum(a!=label and b==label for a,b in zip(gold,pred))
    fn=sum(a==label and b!=label for a,b in zip(gold,pred))
    return 2*tp/max(1,2*tp+fp+fn)

def extraction_scores(tp,fp,fn):
    return {'precision':round(tp/max(1,tp+fp),4),'recall':round(tp/max(1,tp+fn),4),
            'f1':round(2*tp/max(1,2*tp+fp+fn),4)}

def cross_search(queries,passages,model,top_k=3):
    # First stage: independent E5+BM25 shortlist. Joint pair scoring comes
    # ONLY after retrieval. CrossEncoder never certifies the procurement fact.
    first=search(queries,passages,'hybrid',8)
    for row in first['queries']:
        pairs=[(row['query'],p['text']) for p in row['top']]
        scores=model.predict(pairs,batch_size=4,show_progress_bar=False)
        row['top']=[p for p,_ in sorted(zip(row['top'],scores),key=lambda x:-float(x[1]))[:top_k]]
    return first

def evaluate(cases,models=(),cross_model=None):
    gold=[];pred=[];legacy=[];tp=fp=fn=0;ltp=lfp=lfn=0
    winner_correct=0;eligible_correct=0;legacy_eligible_correct=0;errors=[]
    retrieval={m:[] for m in models}
    # Cache repeated offer/query combinations across synthetic variants.
    cache={}
    for case in cases:
        tz=case['tz'];offers=[(o['name'],o['text']) for o in case['offers']]
        report=analyze_documents(tz,offers)
        report['ranking']=build_ranking(report)
        winner_correct+=report['ranking']['recommended']==case['expected_winner']
        expected={c['line'] for c in case['criteria']}
        found=[r.get('line') for r in report['requirements']]
        matched=len(set(found)&expected);tp+=matched;fp+=len(found)-matched;fn+=len(expected)-matched
        # Legacy baseline uses the old numeric field recognizer and operators.
        old=_items(tz,True)
        old_found=[r.get('line') for r in old]
        m=len(set(old_found)&expected);ltp+=m;lfp+=len(old_found)-m;lfn+=len(expected)-m
        for offer,supplier in zip(case['offers'],report['suppliers']):
            checks={c.get('requirement_locator',{}).get('line',c.get('requirement_locator',{}).get('value')):c for c in supplier['checks']}
            old_by_line={r['line']:r for r in old}
            facts={f['key']:f for f in _items(offer['text'],False)}
            got=[];old_got=[]
            for criterion,target in zip(case['criteria'],offer['statuses']):
                status=checks.get(criterion['line'],{}).get('status','unknown')
                got.append(status)
                gold.append(target);pred.append(status)
                req=old_by_line.get(criterion['line'])
                fact=facts.get(req['key']) if req else None
                prior='unknown'
                if req and fact:
                    a,b=fact['value'],req['value']
                    valid=a>=b if req['operator']=='min' else a<=b if req['operator']=='max' else abs(a-b)<1e-8
                    prior='pass' if valid else 'fail'
                old_got.append(prior);legacy.append(prior)
                if status!=target:
                    errors.append({'case':case['id'],'supplier':offer['name'],'parameter':criterion['parameter'],'gold':target,'predicted':status})
            eligible_correct+=(all(x=='pass' for x in got)==all(x=='pass' for x in offer['statuses']))
            legacy_eligible_correct+=(all(x=='pass' for x in old_got)==all(x=='pass' for x in offer['statuses']))
            if models:
                passages=split_text(offer['text'],offer['name'])
                queries=[c['source'] for c in case['criteria']]
                for model in models:
                    key=(model,tuple(queries),offer['text'])
                    if key not in cache:
                        cache[key]=cross_search(queries,passages,cross_model) if model=='cross_encoder' else search(queries,passages,model,3)
                    output=cache[key]
                    for q,truth in zip(output['queries'],offer['evidence']):
                        if not truth:continue # No source means retrieval is not scored as a hit.
                        # Deduplicate chunks of the same line before scoring.
                        seen=set();relevance=[]
                        for p in q['top']:
                            line=p['line']
                            relevance.append(int(line in truth and line not in seen))
                            seen.add(line)
                        recall=sum(relevance)/len(truth)
                        rr=next((1/(i+1) for i,v in enumerate(relevance) if v),0)
                        dcg=sum(v/math.log2(i+2) for i,v in enumerate(relevance))
                        ideal=sum(1/math.log2(i+2) for i in range(min(3,len(truth))))
                        retrieval[model].append((recall,rr,dcg/max(ideal,1e-12)))
    def status_metrics(p):
        return {'accuracy':round(sum(a==b for a,b in zip(gold,p))/len(gold),4),
                'macro_f1':round(sum(f1(gold,p,l) for l in CLASSES)/len(CLASSES),4),
                'f1_by_status':{l:round(f1(gold,p,l),4) for l in CLASSES}}
    return {'cases':len(cases),'supplier_decisions':2*len(cases),'checks':len(gold),
            'note':'Synthetic only; cases share templates. Extraction metric is source-line coverage (not universal atomic extraction).',
            'legacy_numeric_baseline':{'extraction':extraction_scores(ltp,lfp,lfn),**status_metrics(legacy),
                'eligible_decision_accuracy':round(legacy_eligible_correct/(2*len(cases)),4)},
            'current_local':{'extraction':extraction_scores(tp,fp,fn),**status_metrics(pred),
                'eligible_decision_accuracy':round(eligible_correct/(2*len(cases)),4),
                'winner_accuracy':round(winner_correct/len(cases),4)},
            'retrieval':{m:{'recall_at_3':round(sum(x[0] for x in v)/max(1,len(v)),4),
                            'mrr_at_3':round(sum(x[1] for x in v)/max(1,len(v)),4),
                            'ndcg_at_3':round(sum(x[2] for x in v)/max(1,len(v)),4),'queries':len(v)}
                         for m,v in retrieval.items()},
            'errors':errors}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--models',nargs='*',choices=['bm25','tfidf','e5','hybrid','cross_encoder'],default=['bm25'])
    p.add_argument('--cross-model',type=Path)
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    model=None
    if 'cross_encoder' in args.models:
        if not args.cross_model or not args.cross_model.is_dir():
            p.error('--cross-model must be a local model directory; no automatic remote download')
        from sentence_transformers import CrossEncoder
        model=CrossEncoder(str(args.cross_model),device='cpu',local_files_only=True)
    data=json.loads(DATA.read_text(encoding='utf-8'))
    output=evaluate(data['cases'],args.models,model)
    rendered=json.dumps(output,ensure_ascii=False,indent=2)
    if args.output:args.output.write_text(rendered,encoding='utf-8')
    print(rendered)

if __name__=='__main__':main()
