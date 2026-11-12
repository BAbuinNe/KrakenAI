"""Safe web retrieval: immediate BM25, optional isolated E5 with a hard memory cap.

A failed encoder must not terminate the API process or invalidate a completed analysis.
The model remains available for research and on hosts with sufficient memory.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from .embedding_search import split_passages
from .retrieval_baseline import bm25_scores

_MIB=1024*1024
_retry_after=0.0

def retrieve_bm25(result, offers, max_checks=80, top_k=3):
    """Retrieve source rows without loading NumPy, ONNX, or a neural model."""
    out=[]; coverage=[]
    texts=dict(offers)
    for supplier in result.get('suppliers',[]):
        name=supplier['name']
        checks=supplier.get('checks',[])
        passages=split_passages(texts.get(name,''),max_passages=5001)
        truncated=len(passages)>5000
        passages=passages[:5000]
        if not passages:continue
        chosen=checks[:max_checks]
        queries=[str(c.get('parameter',''))+' '+str(c.get('criterion_text') or c.get('requirement_source','')) for c in chosen]
        scores=bm25_scores([p['quote'] for p in passages],queries)
        by_line={}
        for i,p in enumerate(passages):by_line.setdefault(p['line'],[]).append(i)
        for c,row in zip(chosen,scores):
            # Keep an independently identified source row visible even when
            # its vocabulary differs from the TZ (e.g. weight vs mass).
            locator=c.get('offer_locator') or {}
            line=locator.get('line')
            source_hits=set(by_line.get(line,[]))
            order=sorted(range(len(passages)),key=lambda i:(i not in source_hits,-row[i],i))[:top_k]
            fragments=[dict(passages[i],bm25_score=round(row[i],6),relevance_score=round(row[i],6)) for i in order if row[i]>0 or i in source_hits]
            out.append({'supplier':name,'section':c.get('section') or c.get('id'),
                'parameter':c.get('parameter'),'requirement_source':c.get('requirement_source'),
                'fragments':fragments})
        coverage.append({'supplier':name,'passages_scanned':len(passages),'passages_indexed':len(passages),
            'checks_total':len(checks),'checks_searched':len(chosen),'scan_truncated':truncated})
    return {'mode':'bm25','model':None,'results':out,'coverage':coverage,
        'limited':any(x['scan_truncated'] or x['checks_total']>x['checks_searched'] for x in coverage),
        'note':'Поиск BM25 по словам и исходным строкам. Оценки поиска не являются вероятностью соответствия.'}

def _cgroup_headroom():
    for max_file,current_file in (
        ('/sys/fs/cgroup/memory.max','/sys/fs/cgroup/memory.current'),
        ('/sys/fs/cgroup/memory/memory.limit_in_bytes','/sys/fs/cgroup/memory/memory.usage_in_bytes')):
        try:
            limit=int(Path(max_file).read_text().strip())
            current=int(Path(current_file).read_text().strip())
            if limit<2**60:return max(0,limit-current)
        except (OSError,ValueError):pass
    return None

def semantic_enabled():
    return os.getenv('EVIDENCE_RERANKER','lexical').strip().lower()=='e5' and os.getenv('E5_WEB_WORKER','1')!='0'

def retrieve_isolated(result,offers):
    """Return E5 results or a short, non-sensitive explanation of fallback."""
    global _retry_after
    if not semantic_enabled():return None,'Семантический поиск отключён в настройках; доступен BM25.'
    if time.monotonic()<_retry_after:return None,'Энкодер временно недоступен; сохранён поиск BM25.'
    if sum(len(t) for _,t in offers)>600000:
        return None,'Документы превышают лимит семантического поиска на демо-сервере; сохранён BM25.'
    try:
        cap=int(os.getenv('E5_WEB_WORKER_MEMORY_MB','360'))*_MIB
    except ValueError:cap=360*_MIB
    cap=max(64*_MIB,min(cap,1536*_MIB))
    headroom=_cgroup_headroom()
    if headroom is not None:
        # Reserve memory for the API, parsers and concurrent small requests.
        cap=min(cap,max(0,headroom-112*_MIB))
    if cap<256*_MIB:
        return None,'Недостаточно свободной памяти для E5; сохранён поиск BM25.'
    env={k:v for k,v in os.environ.items() if k.startswith(('E5_','EVIDENCE_')) or k in ('PATH','LANG','APP_ENV','PYTHONPATH','PYTHONDONTWRITEBYTECODE','HOME')}
    env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
        TOKENIZERS_PARALLELISM='false',E5_WORKER_ADDRESS_LIMIT=str(cap),E5_WORKER_BATCH='1')
    # Only send the metadata the retrieval algorithm needs, not full reports.
    payload={'result':{'suppliers':[{'name':s['name'],'checks':s.get('checks',[])[:80]} for s in result.get('suppliers',[])]},'offers':offers}
    try:
        p=subprocess.run([sys.executable,'-m','app.web_evidence'],input=json.dumps(payload,ensure_ascii=False),
            capture_output=True,text=True,timeout=55,check=False,env=env)
        if p.returncode!=0:raise RuntimeError('worker failed')
        data=json.loads(p.stdout)
        if not isinstance(data,dict) or data.get('mode') not in ('e5','e5_bm25','none'):raise ValueError('invalid worker result')
        return data,None
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired):
        _retry_after=time.monotonic()+300
        return None,'E5 не завершился в пределах ресурсов сервера; сохранены BM25 и проверенные результаты.'

def _worker():
    # Apply the limit BEFORE importing ONNX/NumPy. A model allocation failure
    # is contained in this process, not in the web API.
    import resource
    cap=int(os.environ['E5_WORKER_ADDRESS_LIMIT'])
    resource.setrlimit(resource.RLIMIT_AS,(cap,cap))
    from .embedding_search import retrieve_e5
    data=json.load(sys.stdin)
    out=retrieve_e5(data['result'],[tuple(x) for x in data['offers']],max_checks=80,top_k=3)
    json.dump(out,sys.stdout,ensure_ascii=False,allow_nan=False)

if __name__=='__main__':_worker()
