"""Render build smoke: authenticated upload -> job polling -> structured result.

No external AI calls, no changes to deployed accounts.
"""
import os
import time
from fastapi.testclient import TestClient

os.environ['APP_PASSWORD'] = 'render-build-smoke-only-not-a-real-password'
os.environ['CHAT_MODE'] = 'rules'
os.environ['EVIDENCE_RERANKER'] = 'lexical'

from .main import app

def run():
    with TestClient(app) as client:
        auth=client.post('/api/login',
            headers={'X-Kraken-Request':'1'},
            json={'password':os.environ['APP_PASSWORD']})
        assert auth.status_code==200,(auth.status_code,auth.text)
        files=[
           ('tz',('terms.txt','Мощность не менее 5 кВт\nЦена не более 100000 руб'.encode('utf-8'),'text/plain')),
           ('proposals',('offer.txt','Мощность 6 кВт\nЦена 90000 руб'.encode('utf-8'),'text/plain'))
        ]
        submitted=client.post('/api/analysis-jobs',files=files,
                              headers={'X-Kraken-Request':'1'})
        assert submitted.status_code==202,submitted.text
        jid=submitted.json()['job_id']
        response=None
        for _ in range(80):
            response=client.get('/api/analysis-jobs/'+jid,
                                headers={'X-Kraken-Request':'1'})
            assert response.status_code==200,response.text
            if response.json()['status']!='processing':break
            time.sleep(.1)
        assert response.json()['status']=='complete',response.text
        result=response.json()['result']
        assert result['suppliers'],result
        assert 'ranking' in result
        assert result['full_report']['total']==1
        assert result['full_report']['suppliers'][0]['position']==1
        assert result['full_report']['suppliers'][0]['checks']
        assert result['document_previews']
        assert result['document_previews'][0]['source_chars']>0
        print('KRAKEN UPLOAD → JOB → ANALYSIS → RANKING SMOKE OK')

if __name__=='__main__':
    run()
