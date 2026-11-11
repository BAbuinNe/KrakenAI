"""Build smoke for expired chat recovery and LLM 404 fallback without API calls."""
import hashlib
import os
import time
import uuid
from fastapi.testclient import TestClient

os.environ['APP_PASSWORD']='smoke-password-not-a-production-secret'
os.environ['CHAT_MODE']='auto'
from .main import app,records,sessions
from . import conversations

def main():
    # Upstream model reports 404 even when the authenticated chat exists:
    # grounded fallback must still answer and send SSE done.
    async def unavailable(*args,**kwargs):
        if False:
            yield ''
        from .ai_stream import ModelStreamError
        raise ModelStreamError('Gemini model unavailable','model_not_found',404)
    previous=conversations.stream_answer
    conversations.stream_answer=unavailable
    original_enabled=conversations.ai.enabled
    conversations.ai.enabled=lambda:True
    try:
        with TestClient(app) as c:
            auth=c.post('/api/login',headers={'X-Kraken-Request':'1'},
                        json={'password':os.environ['APP_PASSWORD']})
            assert auth.status_code==200,auth.text
            key=hashlib.sha256(c.cookies['kraken_session'].encode()).hexdigest()
            rid=uuid.uuid4().hex
            records[rid]={'owner':key,'created':time.time(),
                'result':{'requirements':[{'parameter':'Мощность'}],
                    'suppliers':[{'name':'Поставщик.txt','checks':[
                        {'parameter':'Мощность','mandatory':True,'status':'fail',
                         'requirement_source':'Мощность не менее 150 кВт',
                         'offer_source':'Мощность 110 кВт'}]}]},
                'documents':[{'role':'tz','name':'ТЗ.txt','text':'Мощность не менее 150 кВт'},
                             {'role':'proposal','name':'Поставщик.txt','text':'Мощность 110 кВт'}],
                'filenames':['ТЗ.txt','Поставщик.txt'],'audit':[]}
            dialog=c.post('/api/conversations',headers={'X-Kraken-Request':'1'},
                          json={'analysis_id':rid})
            assert dialog.status_code==200,dialog.text
            cid=dialog.json()['id']
            response=c.post('/api/conversations/'+cid+'/stream',
                   headers={'X-Kraken-Request':'1'},
                   json={'message':'Почему выбранный поставщик подходит или не подходит?'})
            assert response.status_code==200,response.text
            assert 'event: delta' in response.text and 'event: done' in response.text
            assert '110 кВт' in response.text and 'event: error' not in response.text
            # Simulate worker restart, then client can identify old CID as missing.
            sessions[key]['conversations'].clear()
            assert c.post('/api/conversations/'+cid+'/stream',
                 headers={'X-Kraken-Request':'1'},
                 json={'message':'Почему не подходит?'}).status_code==404
            print('KRAKEN GEMINI 404 GROUNDED FALLBACK AND EXPIRED CHAT SMOKE OK',flush=True)
    finally:
        conversations.stream_answer=previous
        conversations.ai.enabled=original_enabled

if __name__=='__main__':
    main()
