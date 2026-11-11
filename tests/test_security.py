import os
os.environ.setdefault('APP_PASSWORD','test_password_at_least_16_characters')
from fastapi.testclient import TestClient
from app.main import app,validate_upload
from fastapi import HTTPException
from docx import Document
from io import BytesIO

client=TestClient(app)
HEAD={'X-Kraken-Request':'1'}

def make_doc(text):
    d=Document()
    for line in text.splitlines(): d.add_paragraph(line)
    out=BytesIO(); d.save(out); return out.getvalue()

def test_unauthorized():
    assert client.get('/api/analyses').status_code==401
    assert client.post('/api/login',json={'password':'bad'},headers=HEAD).status_code==401
    assert client.post('/api/login',json={'password':os.getenv('APP_PASSWORD')}).status_code==403

def test_bad_file_rejection():
    for name,data in [('hack.php',b'<?php'),('../evil.pdf',b'%PDF-1.4'),('fake.docx',b'evil')]:
        try: validate_upload(name,data)
        except HTTPException: pass
        else: raise AssertionError(name)

def test_login_and_real_documents():
    c=TestClient(app)
    assert c.post('/api/login',json={'password':os.getenv('APP_PASSWORD')},headers=HEAD).status_code==200
    tz=make_doc('Мощность не менее 5 кВт\nЦена не более 100000 руб')
    a=make_doc('Мощность 6 кВт\nЦена 90000 руб')
    b=make_doc('Мощность 3 кВт\nЦена 80000 руб')
    files=[('tz',('ТЗ.docx',tz,'application/vnd.openxmlformats-officedocument.wordprocessingml.document')),
           ('proposals',('А.docx',a,'application/vnd.openxmlformats-officedocument.wordprocessingml.document')),
           ('proposals',('Б.docx',b,'application/vnd.openxmlformats-officedocument.wordprocessingml.document'))]
    r=c.post('/api/analyses',files=files,headers=HEAD)
    assert r.status_code==200,r.text
    body=r.json()
    assert body['result']['recommended']=='А.docx'
    report=c.get('/api/analyses/'+body['id']+'/report')
    assert report.status_code==200
    assert 'А.docx' in report.text
    c.post('/api/logout',headers=HEAD)
    assert c.get('/api/analyses/'+body['id']).status_code==401


def test_txt_names_with_cyrillic_spaces_and_browser_fakepath():
    valid=[
        'ТЗ.txt',
        'КП №1 (редакция 2026).TXT',
        'Коммерческое предложение — '+('характеристики ' * 9)+'.txt',
        r'C:\\fakepath\\ТЗ — ноутбуки.txt',
    ]
    for name in valid:
        assert validate_upload(name,'Привет, ТЗ и КП'.encode('utf-8'))=='.txt'

def test_unsafe_txt_paths_still_rejected():
    names=[
        '../hidden.txt',r'C:\\Users\\secret\\KP.txt',
        r'C:\\fakepath\\..\\hidden.txt',
        'file\x00.txt','file\n.txt','x'*260+'.txt',
    ]
    for name in names:
        try:
            validate_upload(name,'Данные'.encode('utf-8'))
        except HTTPException:
            pass
        else:
            raise AssertionError('Unsafe path accepted: '+repr(name))


def test_real_txt_upload_with_long_russian_filename():
    c=TestClient(app)
    assert c.post('/api/login',
        json={'password':os.getenv('APP_PASSWORD')},headers=HEAD).status_code==200
    long_name='Коммерческое предложение '+('оборудование ' * 11)+'.txt'
    files=[
        ('tz',('Техническое задание №2.txt',
               'Мощность не менее 5 кВт'.encode('utf-8'),'text/plain')),
        ('proposals',(long_name,
               'Мощность 6 кВт'.encode('utf-8'),'text/plain')),
    ]
    result=c.post('/api/analyses',files=files,headers=HEAD)
    assert result.status_code==200,result.text
    assert result.json()['result']['suppliers'][0]['name']==long_name[:100]
