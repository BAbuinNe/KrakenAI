"""Ranking invariants and API isolation for pilot procurement analysis."""
import io
import os
import math
import pytest
from app.analysis import analyze_documents
from app.ranking import build_ranking, clean_inputs
from docx import Document
from fastapi.testclient import TestClient
from app.main import app

os.environ.setdefault('APP_PASSWORD','test_password_at_least_16_characters')
HEAD = {'X-Kraken-Request':'1'}
MIME='application/vnd.openxmlformats-officedocument.wordprocessingml.document'

def sample():
    return analyze_documents(
        'Мощность не менее 5 кВт\nЦена не более 100000 руб\nСрок поставки не более 14 дн',
        [('A.docx','Мощность 6 кВт\nЦена 92000 руб\nСрок поставки 10 дн'),
         ('B.docx','Мощность 6 кВт\nЦена 70000 руб\nСрок поставки 14 дн'),
         ('C.docx','Мощность 3 кВт\nЦена 50000 руб\nСрок поставки 7 дн')])

def document(text):
    d=Document()
    for line in text.splitlines():d.add_paragraph(line)
    buf=io.BytesIO()
    d.save(buf)
    return buf.getvalue()

def test_different_weights_change_leader():
    result=sample()
    cheap=build_ranking(result,{'compliance':10,'price':90,'delivery':0,'reliability':0})
    quick=build_ranking(result,{'compliance':10,'price':0,'delivery':90,'reliability':0})
    assert cheap['recommended']=='B.docx'
    assert quick['recommended']=='A.docx'
    assert len(cheap['excluded'])==1
    assert cheap['excluded'][0]['supplier']=='C.docx'
    assert sum(c['contribution'] for c in cheap['ranked'][0]['components'].values())==pytest.approx(cheap['ranked'][0]['score'],abs=.1)

def test_missing_criteria_are_not_made_up():
    r=analyze_documents('Мощность не менее 5 кВт',[('A','Мощность 6 кВт'),('B','Мощность 6 кВт')])
    ranked=build_ranking(r,{'compliance':30,'price':25,'delivery':30,'reliability':15})
    assert ranked['recommended'] is None # tied compliance values
    assert ranked['active_criteria']==['compliance']
    assert len(ranked['unavailable'])==3

def test_bad_weights_and_invalid_reliability():
    r=sample()
    for bad in [{'compliance':0,'price':0,'delivery':0,'reliability':0},
                {'compliance':-1,'price':1,'delivery':0,'reliability':0},
                {'compliance':math.inf,'price':0,'delivery':0,'reliability':0}]:
        with pytest.raises(ValueError):build_ranking(r,bad)
    with pytest.raises(ValueError):
        build_ranking(r,reliability={'Not an offer':65})

def test_original_source_locations():
    r=analyze_documents('Страница 1:\nМощность не менее 5 кВт',
       [('A.pdf','Страница 2:\nМощность 6 кВт')])
    check=r['suppliers'][0]['checks'][0]
    assert check['requirement_locator']=={'kind':'page','value':1,'line':2}
    assert check['offer_locator']=={'kind':'page','value':2,'line':2}

def test_api_changes_are_session_scoped():
    a,b=TestClient(app),TestClient(app)
    for c in (a,b):
        assert c.post('/api/login',json={'password':os.environ['APP_PASSWORD']},headers=HEAD).status_code==200
    files=[('tz',('tz.docx',document('Мощность не менее 5 кВт\nЦена не более 100000 руб'),MIME)),
           ('proposals',('A.docx',document('Мощность 6 кВт\nЦена 92000 руб'),MIME)),
           ('proposals',('B.docx',document('Мощность 6 кВт\nЦена 75000 руб'),MIME))]
    response=a.post('/api/analyses',files=files,headers=HEAD)
    assert response.status_code==200,response.text
    rid=response.json()['id']
    body={'weights':{'compliance':20,'price':80,'delivery':0,'reliability':0},'reliability':{}}
    assert b.post(f'/api/analyses/{rid}/ranking',json=body,headers=HEAD).status_code==404
    updated=a.post(f'/api/analyses/{rid}/ranking',json=body,headers=HEAD)
    assert updated.status_code==200,updated.text
    assert updated.json()['result']['ranking']['recommended']=='B.docx'
    bad={'weights':{'compliance':0,'price':0,'delivery':0,'reliability':0}}
    assert a.post(f'/api/analyses/{rid}/ranking',json=bad,headers=HEAD).status_code==422
    assert len(a.get(f'/api/analyses/{rid}/audit').json()['entries'])==1
    assert b.get(f'/api/analyses/{rid}/audit').status_code==404
