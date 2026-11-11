"""User-facing conversation lifecycle and SSE regression tests."""
import os
os.environ.setdefault('APP_PASSWORD', 'test_password_at_least_16_characters')
from fastapi.testclient import TestClient
from app.main import app

H = {'X-Kraken-Request': '1'}

def sign_in(client):
    response=client.post('/api/login',headers=H,
        json={'password':os.environ['APP_PASSWORD']})
    assert response.status_code == 200

def test_session_conversations_and_sse(monkeypatch):
    monkeypatch.delenv('AI_API_KEY',raising=False)
    monkeypatch.delenv('AI_MODEL',raising=False)
    monkeypatch.setenv('AI_BACKEND','remote')
    a=TestClient(app); b=TestClient(app)
    sign_in(a);sign_in(b)
    created=a.post('/api/conversations',headers=H,json={'title':'Новый чат'})
    assert created.status_code==200
    cid=created.json()['id']
    assert len(a.get('/api/conversations').json())>=1
    assert b.get('/api/conversations/'+cid).status_code==404
    reply=a.post('/api/conversations/'+cid+'/stream',headers=H,
                 json={'message':'Привет, Kraken!'})
    assert reply.status_code==200,reply.text
    assert 'event: delta' in reply.text
    assert 'event: done' in reply.text
    chat=a.get('/api/conversations/'+cid).json()
    assert len(chat['messages'])==2
    assert chat['messages'][0]['role']=='user'
    assert chat['messages'][1]['role']=='assistant'
    assert 'Привет' in chat['title']
    repeat=a.post('/api/conversations/'+cid+'/stream',headers=H,json={'retry':True})
    assert repeat.status_code==200
    assert len(a.get('/api/conversations/'+cid).json()['messages'])==2
    renamed=a.patch('/api/conversations/'+cid,headers=H,json={'title':'Закупка'})
    assert renamed.status_code==200
    assert renamed.json()['title']=='Закупка'
    assert b.delete('/api/conversations/'+cid,headers=H).status_code==404
    assert a.delete('/api/conversations/'+cid,headers=H).status_code==200
    assert a.get('/api/conversations/'+cid).status_code==404

def test_invalid_empty_stream_and_other_session():
    c=TestClient(app);sign_in(c)
    cid=c.post('/api/conversations',headers=H,json={}).json()['id']
    assert c.post('/api/conversations/'+cid+'/stream',headers=H,
                  json={'message':''}).status_code==422
    assert c.post('/api/conversations/'+cid+'/stream',headers=H,
                  json={'retry':True}).status_code==422
    assert c.post('/api/conversations/not-a-chat/stream',headers=H,
                  json={'message':'hi'}).status_code==404


def test_analysis_linked_chat_and_evidence_session_isolation():
    from app.main import records, sessions
    from app.evidence import retrieve_evidence
    c=TestClient(app); sign_in(c)
    # The test uses synthetic, non-confidential extracted text only.
    import time, uuid
    key=next(iter(sessions.keys().__reversed__()))
    rid=uuid.uuid4().hex
    records[rid]={
        'owner':key,'created':time.time(),'filenames':['tz.pdf','vendor.pdf'],
        'result':{'requirements':[{'key':'power'}],
                  'suppliers':[{'name':'vendor.pdf','failed':0,'unknown':1}]},
        'documents':[{'role':'tz','name':'tz.pdf','text':'Страница 2:\nМощность не менее 5 кВт'},
                     {'role':'proposal','name':'vendor.pdf','text':'Страница 4:\nМощность 5500 Вт'}],
        'audit':[]}
    new=c.post('/api/conversations',headers=H,
        json={'title':'Анализ 001','analysis_id':rid})
    assert new.status_code==200
    payload=new.json()
    assert payload['analysis_id']==rid
    assert len(payload['messages'])==1
    evidence=retrieve_evidence(records[rid]['documents'],'Какая мощность?',10)
    assert any(e['location']=='стр. 2' for e in evidence)
    assert any(e['location']=='стр. 4' for e in evidence)
    assert c.get('/api/conversations/'+payload['id']).json()['analysis_id']==rid
    second=TestClient(app);sign_in(second)
    blocked=second.post('/api/conversations',headers=H,
        json={'analysis_id':rid})
    assert blocked.status_code==404


def test_linked_analysis_chat_provides_source_evidence_to_model(monkeypatch):
    """Chat linked to a report can answer from the owner's source text."""
    import hashlib
    import time
    import uuid
    from app.main import records
    import app.conversations as module
    monkeypatch.setenv("AI_BACKEND","gemini")
    monkeypatch.setenv("GEMINI_MODEL","gemini-3.8-flash")
    monkeypatch.setenv("GEMINI_API_KEY","mock-only-never-send")
    client=TestClient(app)
    sign_in(client)
    session=hashlib.sha256(client.cookies['kraken_session'].encode()).hexdigest()
    rid=uuid.uuid4().hex
    records[rid]={'owner':session,'created':time.time(),'audit':[],
      'result':{'requirements':[{'key':'power'}],
                'suppliers':[{'name':'vendor.pdf','failed':0,'unknown':0,'checks':[]}]},
      'documents':[
         {'name':'requirements.pdf','role':'tz','text':'Страница 1:\nМощность не менее 5 кВт'},
         {'name':'vendor.pdf','role':'proposal','text':'Страница 3:\nМощность 5500 Вт'}]}
    seen=[]
    async def mocked_answer(question,result,history,evidence=None):
        assert question=='Какая мощность?'
        assert result is records[rid]['result']
        assert any(x['document']=='vendor.pdf' and x['location']=='стр. 3' for x in evidence)
        assert any(x['document']=='requirements.pdf' for x in evidence)
        seen.append(evidence)
        yield 'В КП указано 5500 Вт. Источник: vendor.pdf, стр. 3.'
    monkeypatch.setattr(module,"stream_answer",mocked_answer)
    created=client.post('/api/conversations',headers=H,json={'analysis_id':rid})
    assert created.status_code==200
    cid=created.json()['id']
    streamed=client.post('/api/conversations/'+cid+'/stream',headers=H,
                         json={'message':'Какая мощность?'})
    assert streamed.status_code==200
    assert 'event: done' in streamed.text
    assert 'vendor.pdf' in streamed.text
    assert len(seen)==1
    restored=client.get('/api/conversations/'+cid).json()
    assert len(restored['messages'])==3
    assert restored['analysis_id']==rid


def test_gemini_404_falls_back_to_evidence_backed_supplier_explanation(monkeypatch):
    import hashlib, time, uuid
    import app.conversations as module
    from app.main import records
    from app.ai_stream import ModelStreamError
    monkeypatch.setenv("CHAT_MODE","auto")
    monkeypatch.setattr(module.ai,"enabled",lambda:True)
    async def broken_model(*args,**kwargs):
        if False:yield ""
        raise ModelStreamError("Модель не найдена","model_not_found",404)
    monkeypatch.setattr(module,"stream_answer",broken_model)
    with TestClient(app) as client:
        sign_in(client)
        key=hashlib.sha256(client.cookies["kraken_session"].encode()).hexdigest()
        rid=uuid.uuid4().hex
        records[rid]={"owner":key,"created":time.time(),"filenames":["ТЗ.txt","КП.txt"],
            "result":{"requirements":[{"id":"2.3","parameter":"Мощность"}],
                      "suppliers":[{"name":"КП.txt","checks":[{"parameter":"Мощность",
                        "mandatory":True,"status":"fail",
                        "requirement_source":"Мощность не менее 150 кВт",
                        "offer_source":"Мощность 110 кВт"}]}]},
            "documents":[{"role":"tz","name":"ТЗ.txt","text":"Мощность не менее 150 кВт"},
                         {"role":"proposal","name":"КП.txt","text":"Мощность 110 кВт"}],
            "audit":[]}
        created=client.post("/api/conversations",headers=H,
                 json={"analysis_id":rid}).json()
        response=client.post("/api/conversations/"+created["id"]+"/stream",
                 headers=H,json={"message":"Почему выбранный поставщик подходит или не подходит?"})
        assert response.status_code==200,response.text
        assert "event: delta" in response.text
        assert "event: done" in response.text
        assert "110 кВт" in response.text
        assert "event: error" not in response.text
