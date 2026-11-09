"""Adversarial regression checks for the pilot, not a substitute for pentesting."""
import io
import os
import zipfile

os.environ.setdefault('APP_PASSWORD','test_password_at_least_16_characters')
from fastapi.testclient import TestClient
from fastapi import HTTPException
from app.main import app, parse_safely
from app.parser_worker import safe_zip

HEAD={'X-Kraken-Request':'1'}
PASS=os.environ['APP_PASSWORD']

def login(client):
    response=client.post('/api/login',json={'password':PASS},headers=HEAD)
    assert response.status_code==200, response.text

def test_prevent_cross_origin_writes():
    c=TestClient(app)
    response=c.post('/api/login',json={'password':PASS},headers={**HEAD,'Origin':'https://evil.example'})
    assert response.status_code==403

def test_security_headers_and_static():
    c=TestClient(app)
    r=c.get('/')
    assert r.status_code==200
    assert r.headers['x-frame-options']=='DENY'
    assert "default-src 'none'" in r.headers['content-security-policy']
    assert r.headers['cache-control']=='no-store'
    assert c.get('/static/app.js').status_code==200
    assert c.get('/api/me').status_code==401

def test_zip_bomb_rejected():
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('word/document.xml', b'a'*(13*1024*1024))
    try: safe_zip(out.getvalue())
    except ValueError: pass
    else: raise AssertionError('ZIP bomb passed validation')

def test_document_isolation_between_sessions():
    from docx import Document
    def docx(text):
        d=Document()
        for line in text.splitlines():d.add_paragraph(line)
        fp=io.BytesIO();d.save(fp);return fp.getvalue()
    a=TestClient(app); b=TestClient(app)
    login(a); login(b)
    tz=docx('Мощность не менее 5 кВт')
    offer=docx('Мощность 6 кВт')
    files=[('tz',('tz.docx',tz,'application/vnd.openxmlformats-officedocument.wordprocessingml.document')),
           ('proposals',('offer.docx',offer,'application/vnd.openxmlformats-officedocument.wordprocessingml.document'))]
    result=a.post('/api/analyses',headers=HEAD,files=files)
    assert result.status_code==200, result.text
    rid=result.json()['id']
    assert a.get('/api/analyses/'+rid).status_code==200
    assert b.get('/api/analyses/'+rid).status_code==404
    assert b.get('/api/analyses/'+rid+'/csv').status_code==404
    assert a.get('/api/analyses/'+rid+'/pdf').status_code==200
    assert a.get('/api/analyses/'+rid+'/report').status_code==200

def test_disallow_invalid_document_content():
    try: parse_safely(b'bad malformed pdf','.pdf')
    except HTTPException as exc: assert exc.status_code==422
    else: raise AssertionError('Malformed PDF accepted')
