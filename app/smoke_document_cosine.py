"""Regression: new default is a cosine table, not criterion extraction."""
import os,io,math,time
from fastapi.testclient import TestClient
os.environ['APP_PASSWORD']='cosine-smoke-not-production-secret'
os.environ['CHAT_MODE']='rules'
os.environ['AI_BACKEND']='disabled'
os.environ['KRAKEN_ANALYSIS_MODE']='cosine'
os.environ['E5_ENABLE_LOCAL']='1'
os.environ['E5_RUNTIME']='onnx'
from .main import app
from .document_cosine import compare,compare_safe,chunks,_score

def main():
    # Real E5 run, not a mock. A clearly unrelated document must rank lower.
    tz='Поставка промышленных насосов. Мощность двигателя 5 кВт. Гарантия 24 месяца.'
    offers=[('other.txt','Рецепт шоколадного пирога. Смешайте муку, сахар, яйца и масло.'),
            ('same.txt',tz),
            ('similar.txt','Коммерческое предложение на насосы. Электродвигатель 6 кВт, гарантия 2 года.')]
    result=compare(tz,offers,'e5')
    assert result['engine']=='document-cosine-v1' and result['method']=='e5',result
    assert result['suppliers'][0]['name']=='same.txt',result
    assert result['suppliers'][-1]['name']=='other.txt',result
    assert result['requirements']==[] and result['recommended'] is None
    for row in result['suppliers']:
        assert math.isclose(row['distance'],1-row['similarity'])
        assert len(row['matches'])==result['tz_chunks']
    assert [s['distance'] for s in result['suppliers']]==sorted(s['distance'] for s in result['suppliers'])
    print('KRAKEN REAL E5 DOCUMENT COSINE SORT OK',flush=True)
    # Exact mathematical aggregation in a two-chunk example.
    score,_=_score([[1,0],[0,1]],[[1,0]],lambda a,b:sum(x*y for x,y in zip(a,b)))
    assert score==0.5
    assert len(chunks('abc '*500))>1
    try:chunks('  ')
    except ValueError:pass
    else:raise AssertionError('empty document accepted')
    # HTTP regression with memory-constrained encoder; the method must be
    # labelled TF-IDF, never pretend it was E5.
    os.environ['E5_WEB_WORKER_MEMORY_MB']='64'
    h={'X-Kraken-Request':'1'}
    with TestClient(app) as c:
        assert c.post('/api/login',json={'password':os.environ['APP_PASSWORD']},headers=h).status_code==200
        files=[('tz',('tz.txt',tz.encode(),'text/plain'))]+[('proposals',(n,t.encode(),'text/plain')) for n,t in offers]
        j=c.post('/api/analysis-jobs',files=files,headers=h)
        assert j.status_code==202,j.text
        jid=j.json()['job_id']
        for _ in range(100):
            payload=c.get('/api/analysis-jobs/'+jid).json()
            if payload['status']!='processing':break
            time.sleep(.1)
        assert payload['status']=='complete',payload
        result=payload['result'];rid=payload['id']
        assert result['method']=='tfidf' and result['fallback_note'],result
        assert result['suppliers'][0]['name']=='same.txt'
        assert result['suppliers'][-1]['name']=='other.txt'
        assert not result['requirements'] and result['recommended'] is None
        assert c.get('/api/analyses/'+rid).json()['engine']=='document-cosine-v1'
        for ext in ('pdf','xlsx','csv','report'):
            export=c.get('/api/analyses/'+rid+'/'+ext)
            assert export.status_code==200 and len(export.content)>100,(ext,export.text[:500])
        dialog=c.post('/api/conversations',json={'analysis_id':rid},headers=h).json()
        assert 'расстояние' in dialog['messages'][0]['content']
        answer=c.post('/api/conversations/'+dialog['id']+'/stream',json={'message':'Какой результат?'},headers=h)
        assert 'event: done' in answer.text and 'TF-IDF' in answer.text,answer.text
    print('KRAKEN COSINE TABLE UPLOAD / FALLBACK / EXPORTS / CHAT SMOKE OK',flush=True)

if __name__=='__main__':main()
