"""HTTP regression for workspace v3: metadata, revisions and real exports."""
import os
import io
import time
from fastapi.testclient import TestClient
os.environ['APP_PASSWORD']='workspace-smoke-only-not-production'
os.environ['CHAT_MODE']='rules'
os.environ['AI_BACKEND']='disabled'
os.environ['EVIDENCE_RERANKER']='lexical'
from .main import app

def main():
    from PIL import Image
    from openpyxl import load_workbook
    from pypdf import PdfReader
    with TestClient(app) as c:
        root=c.get('/')
        assert root.status_code==200
        assert 'og:image' in root.text and 'twitter:card' in root.text and '__PUBLIC_ORIGIN__' not in root.text
        assert Image.open(io.BytesIO(c.get('/favicon.png').content)).size==(96,96)
        assert Image.open(io.BytesIO(c.get('/preview.png').content)).size==(1200,630)
        assert 'Disallow: /api/' in c.get('/robots.txt').text
        assert c.get('/api/analyses').status_code==401
        headers={'X-Kraken-Request':'1'}
        assert c.post('/api/login',json={'password':os.environ['APP_PASSWORD']},headers=headers).status_code==200
        scope=c.get('/api/me').json()['archive_scope']
        assert len(scope)==32 and c.get('/api/me').json()['archive_scope']==scope
        files=[
            ('tz',('ТЗ.txt','Мощность: не менее 5 кВт\nГарантия: не менее 24 месяцев'.encode(),'text/plain')),
            ('proposals',('КП.txt','Поставщик: ООО «ВекторГидро»\nМощность: 6 кВт\nГарантия: 12 месяцев'.encode(),'text/plain'))]
        reply=c.post('/api/analysis-jobs',files=files,headers=headers)
        assert reply.status_code==202,reply.text
        jid=reply.json()['job_id']
        for _ in range(100):
            payload=c.get('/api/analysis-jobs/'+jid).json()
            if payload['status']!='processing':break
            time.sleep(.1)
        assert payload['status']=='complete',payload
        rid=payload['id'];result=payload['result']
        assert result['criteria_editable'] and result['suppliers'][0]['display_name']=='ООО «ВекторГидро»'
        assert result['recommended'] is None
        req=result['requirements'][1]
        assert req['criterion_text']=='не менее 24 месяцев'
        invalid=c.post('/api/analyses/'+rid+'/criteria',json={'edits':[{'id':'bad-id','parameter':'Гарантия','condition':'12 месяцев'}]},headers=headers)
        assert invalid.status_code==422,invalid.text
        revised=c.post('/api/analyses/'+rid+'/criteria',json={'edits':[{'id':req['id'],'parameter':'Гарантия','condition':'не менее 12 месяцев','mandatory':True}]},headers=headers)
        assert revised.status_code==200,revised.text
        revision=revised.json();nr=revision['result'];newid=revision['id']
        assert newid!=rid and nr['revision_of']==rid
        assert nr['recommended']=='КП.txt',nr
        ch=nr['suppliers'][0]['checks'][1]
        assert ch['status']=='pass' and ch['edited']
        assert ch['criterion_text']=='не менее 12 месяцев'
        assert '24 месяцев' in ch['requirement_source'],ch
        assert c.get('/api/analyses/'+rid).json()['suppliers'][0]['checks'][1]['status']=='fail'
        assert c.get('/api/analyses/'+newid).json()['recommended']=='КП.txt'
        assert len(c.get('/api/analyses').json())==2
        x=c.get('/api/analyses/'+newid+'/xlsx')
        assert x.status_code==200,x.text
        wb=load_workbook(io.BytesIO(x.content))
        assert 'Уточнения' in wb.sheetnames
        assert '12 месяцев' in str(list(wb['Сравнение поставщиков'].values))
        pdf=c.get('/api/analyses/'+newid+'/pdf')
        assert pdf.status_code==200,pdf.text
        doc=PdfReader(io.BytesIO(pdf.content))
        all_text=' '.join(p.extract_text() for p in doc.pages)
        assert 'Уточнение пользователя' in all_text and '24 месяцев' in all_text,all_text
        c.post('/api/logout',headers=headers)
        assert c.get('/api/analyses/'+newid).status_code==401
    print('KRAKEN WORKSPACE V3 META / FAVICON / CRITERIA REVISION / PDF / XLSX SMOKE OK',flush=True)

if __name__=='__main__':main()
