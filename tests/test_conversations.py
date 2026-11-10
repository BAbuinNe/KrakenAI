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
