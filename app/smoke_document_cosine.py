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
    # Production must refuse to fabricate a ranking if E5 cannot run.
    os.environ['E5_WEB_WORKER_MEMORY_MB']='64'
    try:compare_safe(tz,offers)
    except RuntimeError:pass
    else:raise AssertionError('unexpected lexical fallback')
    # Run the HTTP flow against genuine E5 vectors already computed above,
    # without depending on a production remote endpoint or secrets in CI.
    from unittest.mock import patch
    from openpyxl import load_workbook
    h={'X-Kraken-Request':'1'}
    with TestClient(app) as c:
        assert c.post('/api/login',json={'password':os.environ['APP_PASSWORD']},headers=h).status_code==200
        files=[('tz',('tz.txt',tz.encode(),'text/plain'))]+[('proposals',(n,t.encode(),'text/plain')) for n,t in offers]
        with patch('app.document_cosine.compare_safe',return_value=result):
            j=c.post('/api/analysis-jobs',files=files,headers=h)
            assert j.status_code==202,j.text
            jid=j.json()['job_id']
            for _ in range(100):
                payload=c.get('/api/analysis-jobs/'+jid).json()
                if payload['status']!='processing':break
                time.sleep(.1)
        assert payload['status']=='complete',payload
        rid=payload['id']
        assert payload['result']['method']=='e5'
        assert payload['result']['suppliers'][0]['name']=='same.txt'
        source=c.get('/api/analyses/'+rid+'/documents/2')
        assert source.status_code==200 and source.json()['name']=='same.txt',source.text
        assert source.json()['text']==tz and source.json()['extracted'] is True
        assert c.get('/api/analyses/'+rid+'/documents/0').json()['role']=='tz'
        assert c.get('/api/analyses/'+rid+'/documents/20').status_code==404
        assert c.get('/api/analyses/'+rid+'/documents/-1').status_code==404
        # The viewing endpoint must never expose procurement text without auth.
        outsider=TestClient(app)
        assert outsider.get('/api/analyses/'+rid+'/documents/2').status_code==401
        for ext in ('pdf','xlsx','csv','report'):
            export=c.get('/api/analyses/'+rid+'/'+ext)
            assert export.status_code==200,(ext,export.text[:500])
            if ext=='xlsx':
                wb=load_workbook(io.BytesIO(export.content));assert wb.active.max_column==2
            if ext=='csv':
                assert export.text.splitlines()[0].lstrip('\ufeff')=='Место,Коммерческое предложение'
        with patch('app.document_cosine.compare_safe',side_effect=RuntimeError('E5 unavailable')):
            j=c.post('/api/analysis-jobs',files=files,headers=h)
            assert j.status_code==202,j.text
            for _ in range(100):
                failed=c.get('/api/analysis-jobs/'+j.json()['job_id']).json()
                if failed['status']!='processing':break
                time.sleep(.1)
        assert failed['status']=='failed' and 'E5 unavailable' in failed['error'],failed
    print('KRAKEN CLEAN E5 RANKING / TWO-COLUMN EXPORT / NO FAKE FALLBACK OK',flush=True)
    print('KRAKEN STRICT E5 NO FALLBACK OK',flush=True)
    print('KRAKEN STRICT COSINE SMOKE OK',flush=True)

if __name__=='__main__':main()
