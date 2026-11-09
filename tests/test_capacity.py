"""T1 regression: ten supplier offers supported, eleven rejected."""
import io
import os
os.environ.setdefault('APP_PASSWORD','test_password_at_least_16_characters')
from docx import Document
from fastapi.testclient import TestClient
from app.main import app

def make_doc(text):
    d=Document();d.add_paragraph(text);buf=io.BytesIO();d.save(buf);return buf.getvalue()

def test_ten_proposals_per_request():
    c=TestClient(app)
    headers={'X-Kraken-Request':'1'}
    assert c.post('/api/login',json={'password':os.environ['APP_PASSWORD']},headers=headers).status_code==200
    mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    tz=make_doc('Мощность не менее 5 кВт')
    cp=make_doc('Мощность 6 кВт')
    files=[('tz',('tz.docx',tz,mime))]+[('proposals',(f'p{i}.docx',cp,mime)) for i in range(10)]
    ok=c.post('/api/analyses',files=files,headers=headers)
    assert ok.status_code==200,ok.text
    assert len(ok.json()['result']['suppliers'])==10
    bad=c.post('/api/analyses',files=files+[('proposals',('p10.docx',cp,mime))],headers=headers)
    assert bad.status_code==400
