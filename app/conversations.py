"""Session-scoped conversations with actual streaming SSE.
Memory-only pilot: chats expire with the login session and are not user accounts.
"""
from __future__ import annotations
import json, time, uuid
from typing import Any, Callable
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from . import ai, chat_fallback
from .ai_stream import stream_answer, ModelStreamError
from .evidence import retrieve_evidence
import logging
logger=logging.getLogger('kraken.conversations')

class Title(BaseModel):
    title:str=Field(default='Новый чат',max_length=90)
    analysis_id:str|None=Field(default=None,max_length=40)

class StreamMessage(BaseModel):
    message:str=Field(default='',max_length=2000)
    analysis_id:str|None=Field(default=None,max_length=40)
    retry:bool=False

def install(app:Any,sessions:dict,auth:Callable,quota:Callable,record:Callable,
            legacy_chat:Callable,legacy_model:type):
    router=APIRouter()
    def chats(key):
        session=sessions.get(key)
        if session is None:raise HTTPException(401,'Сессия истекла')
        return session.setdefault('conversations',{})
    def get(cid,key):
        item=chats(key).get(cid)
        if not item:raise HTTPException(404,'Диалог не найден')
        return item
    def evt(name,data):
        return 'event: '+name+'\ndata: '+json.dumps(data,ensure_ascii=False)+'\n\n'

    @router.get('/api/conversations')
    async def list_items(key:str=Depends(auth)):
        return [{'id':v['id'],'title':v['title'],'updated':v['updated']}
          for v in sorted(chats(key).values(),key=lambda c:c['updated'],reverse=True)]

    @router.post('/api/conversations')
    async def new(body:Title,key:str=Depends(auth)):
        bucket=chats(key)
        if len(bucket)>=30:
            oldest=min(bucket.values(),key=lambda x:x['updated'])
            bucket.pop(oldest['id'],None)
        cid=uuid.uuid4().hex
        initial=[]
        if body.analysis_id:
            analysis=record(body.analysis_id,key)['result']  # owner validated by main
            suppliers=analysis.get('suppliers',[])
            issues=sum(item.get('failed',0) for item in suppliers)
            unknown=sum(item.get('unknown',0) for item in suppliers)
            summary=(f"Готово: обработано {len(suppliers)} КП. "
                     f"Обнаружено {len(analysis.get('requirements',[]))} типов числовых требований, "
                     f"нарушений — {issues}, непроверенных сопоставлений — {unknown}. "
                     "Это предварительная проверка, а не подтверждение полного соответствия ТЗ. "
                     "Откройте аналитику для исходных цитат или спросите меня о конкретном пункте.")
            initial=[{'role':'assistant','content':summary}]
        bucket[cid]={'id':cid,'title':body.title.strip() or 'Новый чат',
                     'updated':time.time(),'messages':initial,
                     'analysis_id':body.analysis_id}
        return {'id':cid,'title':bucket[cid]['title'],'messages':initial,
                'analysis_id':body.analysis_id}

    @router.get('/api/conversations/{cid}')
    async def read(cid:str,key:str=Depends(auth)):
        c=get(cid,key)
        return {'id':cid,'title':c['title'],'messages':c['messages'],
                'analysis_id':c['analysis_id']}

    @router.patch('/api/conversations/{cid}')
    async def rename(cid:str,body:Title,key:str=Depends(auth)):
        c=get(cid,key);c['title']=body.title.strip() or 'Новый чат';c['updated']=time.time()
        return {'id':cid,'title':c['title']}

    @router.delete('/api/conversations/{cid}')
    async def delete(cid:str,key:str=Depends(auth)):
        bucket=chats(key)
        if cid not in bucket:raise HTTPException(404,'Диалог не найден')
        del bucket[cid]
        return {'deleted':True}

    @router.post('/api/conversations/{cid}/stream')
    async def stream(cid:str,body:StreamMessage,key:str=Depends(auth)):
        quota(key,'chat',30,600)
        c=get(cid,key)
        if c.get('generating'):raise HTTPException(409,'Уже идёт генерация ответа')
        original=list(c['messages'])
        if body.retry:
            index=next((i for i in range(len(original)-1,-1,-1)
                        if original[i]['role']=='user'),None)
            if index is None:raise HTTPException(422,'Нет запроса для повтора')
            question=original[index]['content'];history=original[:index]
        else:
            question=body.message.strip();history=original
            if not question:raise HTTPException(422,'Сообщение пустое')
        linked_analysis=body.analysis_id or c.get('analysis_id')
        linked=record(linked_analysis,key) if linked_analysis else None
        context=linked['result'] if linked else None
        evidence=retrieve_evidence(linked.get('documents',[]),question) if linked else []
        c['generating']=True
        async def chunks():
            answer=''
            try:
                if chat_fallback.active() or not ai.enabled():
                    answer=chat_fallback.respond(question, context, evidence)
                    yield evt('delta',{'text':answer})
                else:
                    try:
                        async for piece in stream_answer(question,context,history,evidence):
                            answer+=piece
                            if len(answer)>14000:raise RuntimeError('Ответ слишком длинный')
                            if piece:yield evt('delta',{'text':piece})
                    except ModelStreamError as exc:
                        logger.warning("AI unavailable: %s; using built-in response",exc.code)
                        if not answer:
                            answer=chat_fallback.respond(question,context,evidence)
                            yield evt('delta',{'text':answer})
                        else:
                            answer+="\n\n[Внешняя модель прервала ответ. Для проверки результатов откройте «Аналитику».]"
                            yield evt('delta',{'text':"\n\n[Внешняя модель прервала ответ. Для проверки результатов откройте «Аналитику».]"})
                if body.retry:
                    c['messages']=history+[{'role':'user','content':question},
                                           {'role':'assistant','content':answer}]
                else:
                    c['messages']=(original+[{'role':'user','content':question},
                          {'role':'assistant','content':answer}])[-40:]
                c['analysis_id']=linked_analysis
                if c['title']=='Новый чат':c['title']=question[:60]
                c['updated']=time.time()
                yield evt('done',{'id':cid,'title':c['title']})
            except ModelStreamError as exc:
                logger.warning("Model stream failed code=%s status=%s", exc.code, exc.status)
                yield evt('error',{'message':str(exc),'code':exc.code})
            except Exception as exc:
                logger.error("Unexpected model stream failure type=%s",type(exc).__name__)
                yield evt('error',{'message':'Внутренняя ошибка генерации. Проверьте логи Render.','code':'internal'})
            finally:c['generating']=False
        return StreamingResponse(chunks(),media_type='text/event-stream',
                headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})
    app.include_router(router)
