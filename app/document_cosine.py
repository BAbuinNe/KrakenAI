"""Document-level cosine ranking; no criterion extraction or eligibility decisions."""
from __future__ import annotations
from collections import Counter
import json, math, os, re, subprocess, sys
from .embedding_search import embed, cosine
from .web_evidence import _cgroup_headroom

ENGINE='document-cosine-v1'
NOTE='Сходство текста не подтверждает выполнение требований ТЗ. Это порядок по смысловой близости, а не решение о допуске.'
MAX_CHUNKS=160

def chunks(text):
    # Consecutive source text, not extracted criteria. Retain all characters.
    text=re.sub(r'\s+',' ',text).strip()
    out=[]
    while text:
        end=min(480,len(text))
        if end<len(text):
            boundary=text.rfind(' ',0,end)
            if boundary>=240:end=boundary
        out.append(text[:end])
        text=text[end:].lstrip()
        if len(out)>MAX_CHUNKS:
            raise ValueError('Документ слишком большой для демо: максимум 160 текстовых фрагментов. Разделите документ на части.')
    if not out:raise ValueError('Документ не содержит извлекаемого текста.')
    return out

def _lexical_vectors(texts):
    # Shared TF-IDF space across TZ and ALL proposals, no mixing of models.
    counters=[Counter(re.findall(r'[\w]+(?:[.,]\d+)?',s.casefold())) for s in texts]
    df=Counter(w for c in counters for w in c)
    n=len(counters)
    out=[]
    for c in counters:
        v={w:(1+math.log(f))*(1+math.log((1+n)/(1+df[w]))) for w,f in c.items()}
        length=math.sqrt(sum(x*x for x in v.values()))
        out.append({w:x/length for w,x in v.items()} if length else {})
    return out

def _sparse_cos(a,b):
    if len(a)>len(b):a,b=b,a
    return sum(x*b.get(w,0) for w,x in a.items())

def _score(q,p,dot):
    # Directed mean nearest-neighbor: every TZ chunk has equal weight.
    # D = mean_i(1 - max_j cos(q_i,p_j)). Sort by increasing D.
    best=[]
    for i,a in enumerate(q):
        j,s=max(enumerate(p),key=lambda item:dot(a,item[1]))
        best.append((i,j,max(-1.,min(1.,dot(a,s)))))
    return sum(s for _,_,s in best)/len(best),best

def compare(tz,offers,method='e5'):
    qs=chunks(tz); parts=[chunks(t) for _,t in offers]
    if method=='e5':
        def encoded(texts):
            vectors=[]
            batch=16 if os.getenv('E5_SERVICE_URL','').strip() else 2
            for i in range(0,len(texts),batch):vectors.extend(embed(texts[i:i+batch]))
            return vectors
        q=encoded(['query: '+t for t in qs])
        vectors=[encoded(['passage: '+t for t in ps]) for ps in parts]
        dot=cosine
    elif method=='tfidf':
        allvec=_lexical_vectors(qs+[p for ps in parts for p in ps])
        q=allvec[:len(qs)];offset=len(qs);vectors=[]
        for ps in parts:
            vectors.append(allvec[offset:offset+len(ps)]);offset+=len(ps)
        dot=_sparse_cos
    else:raise ValueError('Unknown cosine method')
    suppliers=[]
    for (name,text),ps,vec in zip(offers,parts,vectors):
        sim,matched=_score(q,vec,dot)
        name_match=re.search(r'^\s*Поставщик\s*:\s*([^\n\r]+)',text,re.I|re.M)
        suppliers.append({'name':name,'display_name':name_match.group(1).strip()[:140] if name_match else name,
            'similarity':sim,'distance':1-sim,'chunks':len(ps),
            'matches':[{'tz_chunk':i+1,'kp_chunk':j+1,'tz_text':qs[i],'kp_text':ps[j],
                        'similarity':s,'distance':1-s} for i,j,s in matched]})
    suppliers.sort(key=lambda x:(x['distance'],x['name'].casefold()))
    for i,s in enumerate(suppliers,1):s['position']=i
    return {'engine':ENGINE,'method':method,'model':'multilingual-E5-small' if method=='e5' else 'TF-IDF',
        'tz_chunks':len(qs),'suppliers':suppliers,'criteria_editable':False,'scope_note':NOTE,
        'aggregation':'mean_best_cosine','recommended':None,'requirements':[],
        'warning':NOTE}

def compare_safe(tz,offers):
    # Never silently substitute a different embedding space in production.
    chunks(tz)
    for _,t in offers:chunks(t)
    if os.getenv('E5_SERVICE_URL','').strip():
        try:
            return compare(tz,offers,'e5')
        except Exception as exc:
            raise RuntimeError('Сервис сравнения временно недоступен. Повторите попытку позже.') from exc
    cap=int(os.getenv('E5_WEB_WORKER_MEMORY_MB','360'))*1024*1024
    headroom=_cgroup_headroom()
    if headroom is not None:cap=min(cap,max(0,headroom-112*1024*1024))
    if cap>=256*1024*1024 and os.getenv('DOCUMENT_E5','1')!='0':
        env={k:v for k,v in os.environ.items() if k.startswith('E5_') or k in ('PATH','LANG','APP_ENV','HOME','PYTHONPATH')}
        env.update(E5_RUNTIME='onnx',E5_ENABLE_LOCAL='1',E5_WORKER_ADDRESS_LIMIT=str(cap),
                   E5_WORKER_BATCH='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
                   TOKENIZERS_PARALLELISM='false')
        try:
            p=subprocess.run([sys.executable,'-m','app.document_cosine'],input=json.dumps({'tz':tz,'offers':offers},ensure_ascii=False),
                             capture_output=True,text=True,timeout=120,env=env)
            if p.returncode==0:
                data=json.loads(p.stdout)
                if data.get('method')=='e5':return data
        except (OSError,ValueError,subprocess.TimeoutExpired):pass
    raise RuntimeError('Недостаточно ресурсов для нейросетевого сравнения. Рейтинг не рассчитан. Повторите попытку позже.')

def answer(question,result):
    rows=result.get('suppliers',[])
    listing='\n'.join(f"{s['position']}. {s['display_name']} — расстояние {s['distance']:.4f}, сходство {s['similarity']:.4f}" for s in rows)
    if any(word in question.casefold() for word in ('косинус','расстояни','сходств','метод','формул')):
        return ('Сравнение текстов ('+result.get('model','')+'):\n\n'+listing+'\n\n'+NOTE)
    return 'Рейтинг КП:\n\n'+'\n'.join(f"{s['position']}. {s['display_name']}" for s in rows)+'\n\n'+NOTE

def _worker():
    import resource
    cap=int(os.environ['E5_WORKER_ADDRESS_LIMIT'])
    resource.setrlimit(resource.RLIMIT_AS,(cap,cap))
    data=json.load(sys.stdin)
    json.dump(compare(data['tz'],data['offers'],'e5'),sys.stdout,ensure_ascii=False,allow_nan=False)

if __name__=='__main__':_worker()
