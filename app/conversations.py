"""Session-scoped conversations with actual streaming SSE.
Memory-only pilot: chats expire with the login session and are not user accounts.
"""
from __future__ import annotations
import json, time, uuid, hashlib, hmac
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

class ChatArchive(BaseModel):
    data:str=Field(min_length=1,max_length=400000)
    mac:str=Field(min_length=64,max_length=64)

class ArchiveRestore(BaseModel):
    archives:list[ChatArchive]=Field(min_length=1,max_length=30)

class StreamMessage(BaseModel):
    message:str=Field(default='',max_length=2000)
    analysis_id:str|None=Field(default=None,max_length=40)
    retry:bool=False

def install(app:Any,sessions:dict,auth:Callable,quota:Callable,record:Callable,
            legacy_chat:Callable,legacy_model:type,archive_secret:Callable):
    router=APIRouter()
    def chats(key):
        # Depends(auth) has already verified the signed cookie. New signed
        # sessions need not exist in the old in-memory session registry.
        # Recreate the temporary chat bucket after a Render restart rather
        # than incorrectly rejecting an authenticated user with HTTP 401.
        session=sessions.setdefault(key,{'conversations':{}})
        return session.setdefault('conversations',{})
    def get(cid,key):
        item=chats(key).get(cid)
        if not item:raise HTTPException(404,'Диалог не найден')
        return item
    def mac(data,key):
        return hmac.new(archive_secret().encode(),('kraken/chat-archive/v1:'+key+':'+data).encode(),hashlib.sha256).hexdigest()
    def snapshot(c,key):
        # Browser stores a signed, bounded transcript. Never include source files,
        # credentials or transient generation flags. Session ownership is MAC-bound.
        item={k:c[k] for k in ('id','title','updated','analysis_id','messages')}
        item['messages']=list(item['messages'])[-40:]
        data=json.dumps(item,ensure_ascii=False,separators=(',',':'))
        while len(data)>300000 and len(item['messages'])>2:
            item['messages']=item['messages'][2:]
            data=json.dumps(item,ensure_ascii=False,separators=(',',':'))
        return {'data':data,'mac':mac(data,key)}
    def trim(bucket):
        for c in sorted(bucket.values(),key=lambda x:x['updated'],reverse=True)[30:]:
            bucket.pop(c['id'],None)
    def evt(name,data):
        return 'event: '+name+'\ndata: '+json.dumps(data,ensure_ascii=False)+'\n\n'

    @router.get('/api/conversations')
    async def list_items(key:str=Depends(auth)):
        return [{'id':v['id'],'title':v['title'],'updated':v['updated'],'archive':snapshot(v,key)}
          for v in sorted(chats(key).values(),key=lambda c:c['updated'],reverse=True)]

    @router.post('/api/conversations/restore')
    async def restore(body:ArchiveRestore,key:str=Depends(auth)):
        quota(key,'chat_restore',30,600)
        bucket=chats(key)
        validated=[]
        for archive in body.archives:
            if not hmac.compare_digest(archive.mac,mac(archive.data,key)):
                raise HTTPException(422,'Копия диалога не принадлежит текущей сессии')
            try:
                item=json.loads(archive.data)
                cid=item['id']
                if uuid.UUID(cid).hex!=cid or not isinstance(item['messages'],list):
                    raise ValueError()
            except (ValueError,KeyError,TypeError):
                raise HTTPException(422,'Некорректная копия диалога') from None
            validated.append(item)
        for item in validated:
            # Never overwrite a newer/live conversation with a browser backup.
            if item['id'] not in bucket:bucket[item['id']]=item
        trim(bucket)
        return {'restored':[item['id'] for item in validated if item['id'] in bucket]}

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
                'analysis_id':body.analysis_id,'archive':snapshot(bucket[cid],key)}

    @router.get('/api/conversations/{cid}')
    async def read(cid:str,key:str=Depends(auth)):
        c=get(cid,key)
        return {'id':cid,'title':c['title'],'messages':c['messages'],
                'analysis_id':c['analysis_id'],'archive':snapshot(c,key)}

    @router.patch('/api/conversations/{cid}')
    async def rename(cid:str,body:Title,key:str=Depends(auth)):
        c=get(cid,key);c['title']=body.title.strip() or 'Новый чат';c['updated']=time.time()
        return {'id':cid,'title':c['title'],'archive':snapshot(c,key)}

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
        try:linked=record(linked_analysis,key) if linked_analysis else None
        except HTTPException as exc:
            if exc.status_code==404:raise HTTPException(409,'История диалога сохранена, но исходный анализ недоступен. Загрузите ТЗ и КП заново для новых вопросов по документам.') from None
            raise
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
                yield evt('done',{'id':cid,'title':c['title'],'archive':snapshot(c,key)})
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
