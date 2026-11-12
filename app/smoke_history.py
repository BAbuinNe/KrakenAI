"""Regression: restore signed chat after process restart and sort real offers."""
import os,json
from fastapi.testclient import TestClient
os.environ['APP_PASSWORD']='history-smoke-only-not-production'
os.environ['CHAT_MODE']='rules'
os.environ['AI_BACKEND']='disabled'
os.environ['EVIDENCE_RERANKER']='lexical'
from .main import app,sessions,records
from .analysis import analyze_documents
from .ranking import build_ranking
from .full_report import build_full_report

def main():
    headers={'X-Kraken-Request':'1'}
    with TestClient(app) as c:
        assert c.post('/api/login',json={'password':os.environ['APP_PASSWORD']},headers=headers).status_code==200
        dialog=c.post('/api/conversations',json={'title':'Мой тест'},headers=headers).json()
        cid=dialog['id']
        response=c.post('/api/conversations/'+cid+'/stream',json={'message':'Как сравнить КП?'},headers=headers)
        assert response.status_code==200 and 'event: done' in response.text,response.text
        done=json.loads(response.text.split('event: done\ndata: ')[1].split('\n')[0])
        saved=done['archive']
        original=c.get('/api/conversations/'+cid).json()['messages']
        assert len(original)==2
        assert len(c.get('/api/conversations').json())==1
        sessions.clear();records.clear()
        assert c.get('/api/conversations').json()==[]
        assert c.post('/api/conversations/restore',json={'archives':[saved]},headers=headers).status_code==200
        reopened=c.get('/api/conversations/'+cid).json()
        assert reopened['messages']==original
        second=c.post('/api/conversations/'+cid+'/stream',json={'message':'Что такое ТЗ?'},headers=headers)
        assert second.status_code==200 and 'event: done' in second.text,second.text
        assert len(c.get('/api/conversations/'+cid).json()['messages'])==4
        assert c.post('/api/conversations/restore',json={'archives':[saved]},headers=headers).status_code==200
        assert len(c.get('/api/conversations/'+cid).json()['messages'])==4
        tampered=dict(saved,data=saved['data']+' ')
        assert c.post('/api/conversations/restore',json={'archives':[tampered]},headers=headers).status_code==422
        # Another authenticated session cannot import this transcript.
        with TestClient(app) as other:
            other.post('/api/login',json={'password':os.environ['APP_PASSWORD']},headers=headers)
            assert other.post('/api/conversations/restore',json={'archives':[saved]},headers=headers).status_code==422
        # The testclient above closes its lifespan, which clears process RAM.
        c.post('/api/conversations/restore',json={'archives':[saved]},headers=headers)
        assert c.delete('/api/conversations/'+cid,headers=headers).status_code==200
        assert c.get('/api/conversations').json()==[]
        assert c.post('/api/logout',headers=headers).status_code==200
        assert c.post('/api/conversations/restore',json={'archives':[saved]},headers=headers).status_code==401
    tz='Мощность: не менее 5 кВт\nМасса: не более 2 кг\nГарантия: не менее 12 месяцев'
    offers=[('bad.txt','Мощность: 3 кВт\nМасса: 3 кг\nГарантия: 12 месяцев'),
            ('good.txt','Мощность: 6 кВт\nМасса: 1 кг\nГарантия: 12 месяцев'),
            ('review.txt','Мощность: 6 кВт\nМасса: 1 кг'),
            ('bad2.txt','Мощность: 4 кВт\nМасса: 1 кг\nГарантия: 12 месяцев')]
    r=analyze_documents(tz,offers);r['ranking']=build_ranking(r)
    report=build_full_report(r)
    assert [s['supplier'] for s in report['suppliers']]==['good.txt','review.txt','bad2.txt','bad.txt'],report
    print('KRAKEN CHAT RESTART RESTORE / SESSION ISOLATION / BEST-TO-WORST SUMMARY SMOKE OK',flush=True)
if __name__=='__main__':main()
