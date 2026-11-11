"""Regression: uploads return a job ID immediately and AI never blocks a comparison."""
import io
import os
import time

from docx import Document
from fastapi.testclient import TestClient
from app.main import app

os.environ.setdefault('APP_PASSWORD', 'test_password_at_least_16_characters')
HEAD = {'X-Kraken-Request': '1'}
MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


def doc(body: str) -> bytes:
    d=Document()
    for row in body.splitlines():
        d.add_paragraph(row)
    stream=io.BytesIO()
    d.save(stream)
    return stream.getvalue()


def test_upload_job_completes_without_waiting_for_ai(monkeypatch):
    from app import ai
    async def should_not_be_called(*args,**kwargs):
        raise AssertionError('Gemini should not block upload')
    monkeypatch.setattr(ai,'supplier_insights',should_not_be_called)
    monkeypatch.setenv('EVIDENCE_RERANKER','lexical')
    with TestClient(app) as client:
        response=client.post('/api/login',json={'password':os.environ['APP_PASSWORD']},headers=HEAD)
        assert response.status_code==200
        files=[
            ('tz',('technical.docx',doc('Мощность не менее 5 кВт'),MIME)),
            ('proposals',('offer.docx',doc('Мощность 6 кВт'),MIME))
        ]
        first=client.post('/api/analysis-jobs',files=files,headers=HEAD)
        assert first.status_code==202,first.text
        jid=first.json()['job_id']
        answer=None
        for _ in range(70):
            item=client.get('/api/analysis-jobs/'+jid,headers=HEAD)
            assert item.status_code==200,item.text
            answer=item.json()
            if answer['status']!='processing':
                break
            time.sleep(.1)
        assert answer['status']=='complete',answer
        assert answer['result']['suppliers'][0]['passed']==1
        assert answer['result']['ai']['status'] in ('deferred','not_configured')


def test_heavy_reranker_is_protected_on_production(monkeypatch):
    from app.neural_reranker import rerank_evidence
    monkeypatch.setenv('APP_ENV','production')
    monkeypatch.setenv('EVIDENCE_RERANKER','cross_encoder')
    monkeypatch.delenv('EVIDENCE_ENABLE_HEAVY',raising=False)
    result=rerank_evidence({'suppliers':[]},[])
    assert result['mode']=='unavailable'
