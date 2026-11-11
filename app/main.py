"""KrakenAI protected prototype. For pilot use; a full security audit is still required."""
from __future__ import annotations
from contextlib import asynccontextmanager
from collections import defaultdict, deque
import base64
import asyncio
import logging
import csv
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import secrets
import subprocess  # nosec B404: fixed-command, no-shell worker with resource limits
import sys
import time
import uuid

from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from .ranking import build_ranking, clean_inputs
from .analysis import analyze_documents
from . import ai

APP_DIR=Path(__file__).parent
MAX_FILE=5*1024*1024
MAX_BODY=60*1024*1024
SESSION_AGE=3*60*60
RECORD_AGE=3*60*60
sessions:dict[str,dict]={}
failed_logins=defaultdict(deque)
request_windows=defaultdict(deque)
records:dict[str,dict]={}
jobs:dict[str,dict]={}
logger=logging.getLogger('kraken.jobs')

def secret_password() -> str:
    password=os.getenv('APP_PASSWORD','')
    if len(password)<16 or password.startswith('REPLACE_WITH_'):
        raise RuntimeError('Установите уникальный APP_PASSWORD длиной не менее 16 символов')
    return password

@asynccontextmanager
async def lifespan(app:FastAPI):
    secret_password()
    if os.getenv('APP_ENV')=='production' and not os.getenv('PUBLIC_ORIGIN','').startswith('https://'):
        raise RuntimeError('Для production нужен HTTPS PUBLIC_ORIGIN')
    yield
    sessions.clear(); records.clear(); jobs.clear(); request_windows.clear()

app=FastAPI(title='KrakenAI Prototype',docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)
app.mount('/static',StaticFiles(directory=APP_DIR/'static'),name='static')

class BodySizeLimit:
    """ASGI-level upload limit even when Content-Length is missing."""
    def __init__(self,app): self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http': return await self.app(scope,receive,send)
        headers=dict(scope.get('headers',[]))
        try: declared=int(headers.get(b'content-length',b'0'))
        except ValueError: declared=MAX_BODY+1
        if declared>MAX_BODY:
            return await JSONResponse({'detail':'Слишком большой запрос'},status_code=413)(scope,receive,send)
        count=0
        async def limited_receive():
            nonlocal count
            msg=await receive()
            if msg.get('type')=='http.request':
                count+=len(msg.get('body',b''))
                if count>MAX_BODY: raise OverflowError('body exceeds limit')
            return msg
        try: await self.app(scope,limited_receive,send)
        except OverflowError:
            return await JSONResponse({'detail':'Слишком большой запрос'},status_code=413)(scope,receive,send)
app.add_middleware(BodySizeLimit)

@app.middleware('http')
async def protect(request:Request,call_next):
    if request.method in ('POST','PUT','DELETE','PATCH'):
        origin=request.headers.get('origin')
        allowed=(os.getenv('PUBLIC_ORIGIN','').rstrip('/') or str(request.base_url).rstrip('/'))
        if origin and origin.rstrip('/')!=allowed:
            return JSONResponse({'detail':'Origin запрещён'},status_code=403)
        if request.headers.get('x-kraken-request')!='1':
            return JSONResponse({'detail':'Требуется заголовок запроса'},status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
    response.headers['Content-Security-Policy']=(
        "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; media-src 'self' data:; font-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    )
    response.headers['Cache-Control']='no-store'
    if os.getenv('APP_ENV')=='production':
        response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
    return response

class LoginForm(BaseModel):
    password:str=Field(min_length=1,max_length=512)

def auth(request:Request)->str:
    raw=request.cookies.get('kraken_session','')
    if not raw: raise HTTPException(401,'Требуется вход')
    key=hashlib.sha256(raw.encode()).hexdigest()
    data=sessions.get(key)
    if not data or data['expires']<time.time():
        sessions.pop(key,None)
        raise HTTPException(401,'Сессия недействительна')
    return key

@app.get('/',response_class=HTMLResponse)
async def root():
    return (APP_DIR/'static/index.html').read_text(encoding='utf-8')

@app.get('/api/me')
async def me(key:str=Depends(auth)):
    return {'authenticated':True,'name':'KrakenAI','ai_enabled':ai.enabled()}

@app.post('/api/login')
async def login(body:LoginForm,request:Request):
    ip=request.client.host if request.client else 'unknown'
    now=time.time()
    attempts=failed_logins[ip]
    while attempts and attempts[0]<now-600: attempts.popleft()
    if len(attempts)>=5: raise HTTPException(429,'Слишком много попыток. Повторите через 10 минут')
    if not hmac.compare_digest(body.password.encode(),secret_password().encode()):
        attempts.append(now)
        raise HTTPException(401,'Неверный пароль')
    attempts.clear()
    token=secrets.token_urlsafe(32)
    key=hashlib.sha256(token.encode()).hexdigest()
    sessions[key]={'expires':now+SESSION_AGE}
    response=JSONResponse({'authenticated':True,'ai_enabled':ai.enabled()})
    response.set_cookie('kraken_session',token,max_age=SESSION_AGE,httponly=True,
                        secure=os.getenv('APP_ENV')=='production',samesite='strict',path='/')
    return response

@app.post('/api/logout')
async def logout(key:str=Depends(auth)):
    sessions.pop(key,None)
    for k in [k for k in request_windows if k[0] == key]: request_windows.pop(k, None)
    for rid in [i for i,r in records.items() if r['owner']==key]: records.pop(rid,None)
    response=JSONResponse({'ok':True})
    response.delete_cookie('kraken_session',path='/')
    return response

def validate_upload(filename:str,content:bytes)->str:
    if not filename or len(filename)>150 or '\x00' in filename or '/' in filename or '\\' in filename:
        raise HTTPException(400,'Недопустимое имя файла')
    ext=Path(filename).suffix.lower()
    if ext not in ('.pdf','.docx','.xlsx','.txt'): raise HTTPException(400,'Разрешены только PDF, DOCX, XLSX и TXT')
    if not content or len(content)>MAX_FILE: raise HTTPException(413,'Каждый файл должен быть не больше 5 МБ')
    if ext=='.pdf' and not content.startswith(b'%PDF-'):
        raise HTTPException(400,'Формат PDF не соответствует содержимому')
    if ext in ('.docx','.xlsx') and not content.startswith(b'PK\x03\x04'):
        raise HTTPException(400,'Формат документа не соответствует содержимому')
    if ext=='.txt':
        if b'\x00' in content: raise HTTPException(400,'Текстовый файл содержит недопустимые двоичные данные')
        try: content.decode('utf-8-sig')
        except UnicodeDecodeError: raise HTTPException(400,'TXT должен быть в кодировке UTF-8') from None
    return ext

def parse_safely(blob:bytes,extension:str)->str:
    payload={'content':base64.b64encode(blob).decode('ascii'),'ext':extension}
    limited_env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),
                 'PYTHONPATH':str(APP_DIR.parent),'PYTHONDONTWRITEBYTECODE':'1',
                 'LANG':'C.UTF-8'}
    try:
        proc=subprocess.run([sys.executable,'-m','app.parser_worker'],input=json.dumps(payload),  # nosec B603: fixed module, no shell
              capture_output=True,text=True,timeout=40,cwd=str(APP_DIR.parent),check=False,env=limited_env)
        body=json.loads(proc.stdout)
    except (subprocess.TimeoutExpired,ValueError,json.JSONDecodeError):
        raise HTTPException(422,'Не удалось обработать документ')
    if proc.returncode or body.get('error'):
        raise HTTPException(422,'Документ повреждён, слишком сложен или не поддерживается')
    text=body.get('text','')
    if len(text.strip())<5: raise HTTPException(422,'В документе нет распознаваемого текста (скан требует OCR)')
    return text

def enforce_quota(key:str,action:str,limit:int,window_seconds:int)->None:
    now=time.time()
    bucket=request_windows[(key,action)]
    while bucket and bucket[0]<now-window_seconds: bucket.popleft()
    if len(bucket)>=limit: raise HTTPException(429,'Превышен лимит запросов. Повторите позже')
    bucket.append(now)

def cleanup():
    now=time.time()
    for rid,r in list(records.items()):
        if r['created']+RECORD_AGE<now: records.pop(rid,None)
    for key,s in list(sessions.items()):
        if s['expires']<now: sessions.pop(key,None)

@app.post('/api/analyses')
async def new_analysis(tz:UploadFile=File(...),proposals:list[UploadFile]=File(...),key:str=Depends(auth)):
    enforce_quota(key,'analysis',10,600)
    if not 1<=len(proposals)<=10: raise HTTPException(400,'Загрузите от 1 до 10 предложений')
    payloads=[]
    for file in [tz,*proposals]:
        data=await file.read(MAX_FILE+1)
        ext=validate_upload(file.filename or '',data)
        payloads.append((file.filename,ext,data))
        await file.close()
    return await _process_payloads(payloads,key)


async def _process_payloads(payloads:list[tuple[str,str,bytes]],key:str,job_id:str|None=None)->dict:
    def progress(stage:str):
        if job_id and job_id in jobs: jobs[job_id]['stage']=stage
    progress('Читаю техническое задание')
    tz_text=await run_in_threadpool(parse_safely,payloads[0][2],payloads[0][1])
    offers=[]
    for name,ext,data in payloads[1:]:
        progress('Читаю коммерческое предложение: '+name[:60])
        offers.append((name,await run_in_threadpool(parse_safely,data,ext)))
    progress('Сравниваю требования с предложениями')
    result=await run_in_threadpool(analyze_documents,tz_text,offers)
    from .neural_reranker import rerank_evidence
    # E5 retrieval is CPU-heavy on Render Free; do not block the ranking.
    result['evidence_retrieval']={'mode':'pending','results':[],
        'note':'Дополнительные доказательства ищутся отдельно; основные проверки готовы'}
    progress('Готовлю рейтинг и отчёт')
    from .text_summary import preview as compact_preview
    result['document_previews']=[
        {'name':name,**compact_preview(body,tz_text)} for name,body in offers
    ]
    result['ranking']=build_ranking(result)
    result['recommended']=result['ranking']['recommended']
    from .full_report import build_full_report
    result['full_report']=build_full_report(result)
    result['decision_summary']={
        'total_offers':len(result.get('suppliers', [])),
        'requirements_extracted':len(result.get('requirements', [])),
        'eligible':sum(
            bool([c for c in supplier.get('checks', []) if c.get('mandatory', True)])
            and not any(c.get('status') != 'pass' for c in supplier.get('checks', [])
                    if c.get('mandatory', True))
            for supplier in result.get('suppliers', [])
        ),
        'rejected':sum(
            any(c.get('status') == 'fail' for c in supplier.get('checks', [])
                if c.get('mandatory', True))
            for supplier in result.get('suppliers', [])
        ),
        'needs_review':sum(
            not any(c.get('status') == 'fail' for c in supplier.get('checks', [])
                    if c.get('mandatory', True))
            and (not any(c.get('mandatory', True) for c in supplier.get('checks', []))
                 or any(c.get('status') == 'unknown' for c in supplier.get('checks', [])
                        if c.get('mandatory', True)))
            for supplier in result.get('suppliers', [])
        ),
        'recommended':result['recommended'],
    }
    # Do not block upload response on an external LLM. It can time out independently.
    from .chat_fallback import active as chat_rules_active
    ai_available=ai.enabled() and not chat_rules_active()
    result['ai']={'enabled':ai_available,'status':'deferred' if ai_available else 'not_configured','observations':[]}
    result['scope_note']=(
        'Требования разделены на отдельные проверяемые условия. Для каждого результата '
        'указаны исходный пункт ТЗ и подтверждающая строка КП. Отсутствующие характеристики '
        'имеют статус «требует проверки», а подтверждённые нарушения обязательных пунктов '
        'исключают предложение из отбора.'
        if result.get('engine') == 'requirements-v2'
        else 'Проверены распознанные числовые требования и предварительные смысловые '
             'наблюдения. Неизвлечённые условия необходимо проверить специалисту.'
    )
    rid=uuid.uuid4().hex
    cleanup()
    records[rid]={'owner':key,'created':time.time(),'result':result,
                  'filenames':[p[0] for p in payloads],'audit':[],
                  'documents':[{'name':payloads[0][0],'role':'tz','text':tz_text}]+
                              [{'name':name,'role':'proposal','text':content}
                               for name,content in offers]}
    asyncio.create_task(_complete_evidence(rid,offers))
    return {'id':rid,'result':result,'filenames':[p[0] for p in payloads]}

# Only one ONNX E5 job at a time on the 512-MiB Render demo.
EVIDENCE_SEMAPHORE=asyncio.Semaphore(1)

async def _complete_evidence(rid:str, offers:list[tuple[str,str]]):
    from .neural_reranker import rerank_evidence
    async with EVIDENCE_SEMAPHORE:
        try:
            entry=records.get(rid)
            if not entry:return
            evidence=await run_in_threadpool(rerank_evidence,entry['result'],offers)
            if rid in records:
                records[rid]['result']['evidence_retrieval']=evidence
        except Exception:
            logger.exception('Evidence indexing failed for analysis %s',rid[:8])
            if rid in records:
                records[rid]['result']['evidence_retrieval']={
                    'mode':'unavailable','results':[],
                    'note':'Поиск выдержек недоступен; основная проверка сохранена'}

# Polling API: document parsing can take longer than reverse-proxy timeouts.
JOB_AGE=12*60

async def _run_analysis_job(jid:str,key:str,payloads:list[tuple[str,str,bytes]]):
    try:
        payload=await _process_payloads(payloads,key,jid)
        if jid in jobs:
            jobs[jid].update(status='complete',analysis_id=payload['id'],result=payload['result'])
    except HTTPException as exc:
        if jid in jobs:
            jobs[jid].update(status='failed',error=str(exc.detail)[:250])
    except Exception:
        logger.exception('Failed to complete analysis job %s',jid[:8])
        if jid in jobs:
            jobs[jid].update(status='failed',
                             error='Анализ не завершился из-за ошибки сервера. Попробуйте меньшие файлы.')

@app.post('/api/analysis-jobs',status_code=202)
async def start_analysis_job(tz:UploadFile=File(...),
                             proposals:list[UploadFile]=File(...),key:str=Depends(auth)):
    enforce_quota(key,'analysis',10,600)
    if not 1<=len(proposals)<=10:
        raise HTTPException(400,'Загрузите от 1 до 10 предложений')
    now=time.time()
    for jid,j in list(jobs.items()):
        if now-j['created']>JOB_AGE: jobs.pop(jid,None)
    if sum(j['status']=='processing' for j in jobs.values())>=3:
        raise HTTPException(429,'Сервер занят обработкой документов. Повторите запрос позже.')
    if any(j['owner']==key and j['status']=='processing' for j in jobs.values()):
        raise HTTPException(409,'У вас уже выполняется анализ. Дождитесь его результата.')
    payloads=[]
    for file in [tz,*proposals]:
        data=await file.read(MAX_FILE+1)
        ext=validate_upload(file.filename or '',data)
        payloads.append((file.filename,ext,data))
        await file.close()
    jid=uuid.uuid4().hex
    jobs[jid]={'owner':key,'created':time.time(),'status':'processing','stage':'Загрузка файлов завершена'}
    asyncio.create_task(_run_analysis_job(jid,key,payloads))
    return {'job_id':jid,'status':'processing'}

@app.get('/api/analysis-jobs/{jid}')
async def get_analysis_job(jid:str,key:str=Depends(auth)):
    job=jobs.get(jid)
    if not job or job['owner']!=key:
        raise HTTPException(404,'Задание не найдено или срок хранения истёк')
    if job['status']=='failed':
        return {'status':'failed','error':job.get('error','Ошибка обработки')}
    if job['status']=='complete':
        return {'status':'complete','id':job['analysis_id'],'result':job['result']}
    return {'status':'processing','stage':job.get('stage','Обрабатываю файлы')}

@app.get('/api/analyses')
async def history(key:str=Depends(auth)):
    cleanup()
    return [{'id':rid,'filenames':r['filenames'],'created':r['created'],
             'recommended':r['result']['recommended']} for rid,r in reversed(list(records.items())) if r['owner']==key]

def get_record(rid:str,key:str)->dict:
    cleanup()
    r=records.get(rid)
    if not r or r['owner']!=key: raise HTTPException(404,'Анализ не найден')
    return r

@app.get('/api/analyses/{rid}')
async def read_analysis(rid:str,key:str=Depends(auth)):
    return get_record(rid,key)['result']

@app.post('/api/analyses/{rid}/insights')
async def analyze_insights(rid:str,key:str=Depends(auth)):
    """Optional AI explanation, outside the time-critical document upload."""
    from .chat_fallback import active as chat_rules_active
    if chat_rules_active():
        raise HTTPException(503,'Дополнительные AI-пояснения временно отключены; основные результаты анализа доступны.')
    enforce_quota(key,'insights',8,600)
    record=get_record(rid,key)
    if record['result'].get('ai',{}).get('status')=='complete':
        return {'ai':record['result']['ai']}
    documents=record.get('documents',[])
    if not documents:
        raise HTTPException(404,'Тексты анализа недоступны')
    tz_text=documents[0]['text']
    offers=[(doc['name'],doc['text']) for doc in documents[1:]]
    insight=await ai.supplier_insights(tz_text,offers,record['result'])
    record['result']['ai']=insight
    return {'ai':insight}

class RankingUpdate(BaseModel):
    weights:dict[str,float] = Field(min_length=4, max_length=4)
    reliability:dict[str,float] = Field(default_factory=dict, max_length=10)

@app.post('/api/analyses/{rid}/ranking')
async def update_ranking(rid:str, body:RankingUpdate, key:str=Depends(auth)):
    enforce_quota(key,'ranking',40,600)
    record=get_record(rid,key)
    try:
        weights, reliability = clean_inputs(body.weights,body.reliability,
            {s['name'] for s in record['result']['suppliers']})
        ranking=build_ranking(record['result'],weights,reliability)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from None
    record['result']['ranking']=ranking
    record['result']['recommended']=ranking['recommended']
    from .full_report import build_full_report
    record['result']['full_report']=build_full_report(record['result'])
    if 'decision_summary' in record['result']:
        record['result']['decision_summary']['recommended']=ranking['recommended']
    record['audit'].append({
        'at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'action':'ranking_changed',
        'actor':'Текущая сессия '+key[:8],
        'weights':weights,
        'manual_reliability':reliability,
    })
    record['result']['audit_log']=record['audit'][-20:]
    return {'result':record['result']}

@app.get('/api/analyses/{rid}/audit')
async def read_audit(rid:str,key:str=Depends(auth)):
    return {'entries':get_record(rid,key).get('audit',[])}

@app.get('/api/analyses/{rid}/report')
async def download_json(rid:str,key:str=Depends(auth)):
    data=json.dumps(get_record(rid,key)['result'],ensure_ascii=False,indent=2)
    return Response(content=data,media_type='application/json; charset=utf-8',
        headers={'Content-Disposition':f'attachment; filename="kraken-report-{rid[:8]}.json"'})

@app.get('/api/analyses/{rid}/csv')
async def download_csv(rid:str,key:str=Depends(auth)):
    result=get_record(rid,key)['result']
    stream=io.StringIO()
    writer=csv.writer(stream)
    writer.writerow(['Поставщик','Параметр','Требование','Предложено','Ед.','Статус','Причина'])
    for s in result.get('suppliers',[]):
        for c in s['checks']:
            def safe(v):
                t=str('' if v is None else v)
                return "'"+t if t.lstrip().startswith(('=','+','-','@','\t','\r')) else t
            writer.writerow([safe(s['name']),safe(c['parameter']),safe(c['required']),safe(c['actual']),
                              safe(c['unit']),safe(c['status']),safe(c['reason'])])
    return Response('\ufeff'+stream.getvalue(),media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition':f'attachment; filename="kraken-report-{rid[:8]}.csv"'})

@app.get('/api/analyses/{rid}/xlsx')
async def download_xlsx(rid:str,key:str=Depends(auth)):
    """Formula-safe Excel export belonging only to the authenticated session."""
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill,Alignment
    result=get_record(rid,key)['result']
    workbook=Workbook()
    sheet=workbook.active
    sheet.title='Сравнение поставщиков'
    overview=workbook.create_sheet('Итоги')
    overview.append(['Поставщик','Решение','Нарушений обязательных','Неизвестных обязательных','Место','Балл'])
    ranked={item.get('supplier'):(index+1,item.get('score'))
            for index,item in enumerate(result.get('ranking',{}).get('ranked',[]))}
    for supplier in result.get('suppliers',[]):
        mandatory=[c for c in supplier.get('checks',[]) if c.get('mandatory',True)]
        failures=sum(c.get('status')=='fail' for c in mandatory)
        unknowns=sum(c.get('status')=='unknown' for c in mandatory)
        decision='Отклонено' if failures else 'Требует уточнения' if unknowns else 'Допущено'
        pos,score=ranked.get(supplier['name'],('',None))
        overview.append([("'"+supplier['name'] if supplier['name'].lstrip().startswith(('=','+','-','@')) else supplier['name']),decision,failures,unknowns,pos,score])
    overview.freeze_panes='A2'
    overview.auto_filter.ref=overview.dimensions
    for col,width in {'A':32,'B':24,'C':28,'D':30,'E':12,'F':12}.items():
        overview.column_dimensions[col].width=width
    for cell in overview[1]:
        cell.font=Font(bold=True,color='FFFFFF')
        cell.fill=PatternFill('solid',fgColor='333333')
    headers=['Поставщик','Параметр','Требование','Оператор','Предложено','Единицы',
             'Статус','Приоритет','Основание ТЗ','Основание КП','Пояснение']
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font=Font(bold=True,color='FFFFFF')
        cell.fill=PatternFill('solid',fgColor='333333')
        cell.alignment=Alignment(wrap_text=True,vertical='center')
    def safe(value):
        if value is None:return ''
        if isinstance(value,(int,float)) and not isinstance(value,bool):return value
        text=str(value)
        return "'"+text if text.lstrip().startswith(('=','+','-','@','\t','\r')) else text
    status_colors=('E8F5EA','FFE9E9','FFF4D5')
    for supplier in result.get('suppliers',[]):
        for check in supplier.get('checks',[]):
            sheet.append([safe(supplier.get('name')),safe(check.get('parameter')),
                safe(check.get('required')),safe(check.get('operator')),
                safe(check.get('actual')),safe(check.get('unit')),safe(check.get('status')),
                'Обязательно' if check.get('mandatory',True) else 'Дополнительно',
                safe(check.get('requirement_source')),safe(check.get('offer_source')),
                safe(check.get('reason'))])
            status=check.get('status')
            fill=(status_colors[0] if status=='pass'
                else status_colors[1] if status=='fail'
                else status_colors[2] if status=='unknown' else None)
            if fill:sheet.cell(sheet.max_row,7).fill=PatternFill('solid',fgColor=fill)
    widths={'A':28,'B':24,'C':18,'D':12,'E':18,'F':12,'G':17,'H':18,'I':48,'J':48,'K':48}
    for column,width in widths.items():sheet.column_dimensions[column].width=width
    sheet.freeze_panes='A2'
    sheet.auto_filter.ref=sheet.dimensions
    sheet.sheet_view.showGridLines=False
    out=io.BytesIO();workbook.save(out)
    return Response(out.getvalue(),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition':f'attachment; filename="kraken-report-{rid[:8]}.xlsx"'})

@app.get('/api/analyses/{rid}/pdf')
async def download_pdf(rid:str,key:str=Depends(auth)):
    import html
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    data=get_record(rid,key)['result']
    font_path='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    if not os.path.exists(font_path): raise HTTPException(503,'Для PDF не установлен шрифт DejaVu Sans')
    if 'DejaVuSansKraken' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('DejaVuSansKraken',font_path))
    style=ParagraphStyle('KrakenText',fontName='DejaVuSansKraken',fontSize=8.5,leading=13,spaceAfter=5)
    title=ParagraphStyle('KrakenTitle',parent=style,fontSize=19,leading=24,spaceAfter=13)
    sub=ParagraphStyle('KrakenSub',parent=style,fontSize=11,leading=16,spaceBefore=11)
    def p(t,st=style): return Paragraph(html.escape(str(t or '—')),st)
    buf=io.BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=A4,leftMargin=36,rightMargin=36,topMargin=40,bottomMargin=40)
    summary=data.get('decision_summary', {})
    items=[p('KrakenAI · Отчёт о сравнении поставщиков',title),
           p('Проверено КП: '+str(summary.get('total_offers', len(data.get('suppliers',[]))))
             +'; выделено требований: '+str(summary.get('requirements_extracted',len(data.get('requirements',[]))))
             +'; допущено: '+str(summary.get('eligible',0))
             +'; отклонено: '+str(summary.get('rejected',0))
             +'; требует уточнения: '+str(summary.get('needs_review',0))),
           p(data.get('warning','')),
           p('Рекомендованный вариант: '+str(data.get('recommended') or 'не определён')),Spacer(1,8)]
    for s in data.get('suppliers',[]):
        mandatory=[c for c in s.get('checks',[]) if c.get('mandatory',True)]
        failures=sum(c.get('status')=='fail' for c in mandatory)
        unknowns=sum(c.get('status')=='unknown' for c in mandatory)
        verdict='Отклонено' if failures else 'Требует уточнения' if unknowns else 'Допущено'
        items.append(p(s['name']+' — '+verdict,sub))
        items.append(p('Обязательных нарушений: '+str(failures)
                       +'; неизвестных обязательных условий: '+str(unknowns)))
        rows=[[p(x) for x in ('Параметр','Требование','Предложено','Результат')]]
        for c in s['checks']:
            unit=c['unit']
            rows.append([p(c['parameter']),p(str(c['required'])+' '+unit),
                         p(str(c['actual'])+' '+unit if c['actual'] is not None else 'Не найдено'),
                         p(('Соответствует' if c['status']=='pass' else 'Расхождение' if c['status']=='fail' else 'Требует проверки'))])
        table=Table(rows,colWidths=[145,125,125,115],repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),'DejaVuSansKraken'),
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#f5f5f5')),
            ('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),7),
            ('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#dddddd'))]))
        items.append(table)
    items.append(Spacer(1,14))
    items.append(p('Выводы системы предварительные; решение о закупке принимает специалист.'))
    doc.build(items)
    return Response(buf.getvalue(),media_type='application/pdf',
        headers={'Content-Disposition':f'attachment; filename="kraken-report-{rid[:8]}.pdf"'})

class ChatRequest(BaseModel):
    message:str=Field(min_length=1,max_length=1000)
    analysis_id:str|None=Field(default=None,max_length=40)

@app.post('/api/chat')
async def chat(body:ChatRequest,key:str=Depends(auth)):
    from . import chat_fallback
    enforce_quota(key,'chat',30,600)
    result=get_record(body.analysis_id,key)['result'] if body.analysis_id else None
    if chat_fallback.active() or not ai.enabled():
        return {'answer':chat_fallback.respond(body.message,result),'mode':'rules'}
    try:
        reply=await ai.answer(body.message,result)
        return {'answer':reply,'mode':'ai'}
    except Exception:
        return {'answer':chat_fallback.respond(body.message,result),'mode':'rules'}

@app.get('/healthz')
async def healthz(): return {'status':'ok'}

# Single-workspace pilot: history is scoped to a session and expires on logout.
from .conversations import install as install_conversations
install_conversations(app,sessions,auth,enforce_quota,get_record,chat,ChatRequest)
