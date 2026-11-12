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
    print('KRAKEN STRICT E5 NO FALLBACK OK',flush=True)
    print('KRAKEN STRICT COSINE SMOKE OK',flush=True)

if __name__=='__main__':main()
