"""Render build smoke: authenticated upload -> job polling -> structured result.

No external AI calls, no changes to deployed accounts.
"""
import os
import time
from fastapi.testclient import TestClient

os.environ['APP_PASSWORD'] = 'render-build-smoke-only-not-a-real-password'
os.environ['CHAT_MODE'] = 'rules'
os.environ['EVIDENCE_RERANKER'] = 'lexical'

from .main import app

def run():
    with TestClient(app) as client:
        auth=client.post('/api/login',
            headers={'X-Kraken-Request':'1'},
            json={'password':os.environ['APP_PASSWORD']})
        assert auth.status_code==200,(auth.status_code,auth.text)
        files=[
           ('tz',('terms.txt','Мощность не менее 5 кВт\nЦена не более 100000 руб'.encode('utf-8'),'text/plain')),
           ('proposals',('offer.txt','Мощность 6 кВт\nЦена 90000 руб'.encode('utf-8'),'text/plain'))
        ]
        submitted=client.post('/api/analysis-jobs',files=files,
                              headers={'X-Kraken-Request':'1'})
        assert submitted.status_code==202,submitted.text
        jid=submitted.json()['job_id']
        response=None
        for _ in range(80):
            response=client.get('/api/analysis-jobs/'+jid,
                                headers={'X-Kraken-Request':'1'})
            assert response.status_code==200,response.text
            if response.json()['status']!='processing':break
            time.sleep(.1)
        assert response.json()['status']=='complete',response.text
        result=response.json()['result']
        assert result['suppliers'],result
        assert 'ranking' in result
        assert result['full_report']['total']==1
        assert result['full_report']['suppliers'][0]['position']==1
        assert result['full_report']['suppliers'][0]['checks']
        assert result['document_previews']
        assert result['document_previews'][0]['source_chars']>0
        print('KRAKEN UPLOAD → JOB → ANALYSIS → RANKING SMOKE OK')

        # Regression for multi-section engine procurement TZ: every clause must
        # survive extraction, including non-numeric and verification-only items.
        from .analysis import analyze_documents
        tz_lines=[
            '2.1. Тип: дизельный, 4-тактный, рядный или V-образный.',
            '2.2. Модель и маркировка: соответствие штатному ДВС ТС.',
            '2.3. Мощность: не менее 150 кВт.',
            '2.4. Рабочий объём: 6,0 л с допуском ±5%.',
            '2.5. Число цилиндров: 6.',
            '2.6. Экологический класс: не ниже Евро-4.',
            '2.7. Система охлаждения: жидкостная.',
            '2.8. Комплектность: блок, ГБЦ, ТНВД, турбокомпрессор, генератор, стартер, форсунки, жгуты, навесное оборудование.',
            '2.9. Состояние: новый.',
            '2.10. Ресурс: не менее 10 000 моточасов.',
            '2.11. Гарантия: не менее 12 месяцев.',
            '3.1. Срок поставки: не более 30 календарных дней.',
            '3.2. Условия поставки: до склада, разгрузка поставщиком.',
            '3.3. Документы: паспорт, сертификат, гарантийный талон, накладная.',
            '3.4. Упаковка: транспортная тара.',
            '4.1. Опыт поставок аналогичной продукции: не менее 3 лет.',
            '4.2. Наличие сервисной поддержки или гарантийного ремонта.',
            '4.3. Отсутствие в реестре недобросовестных поставщиков.',
        ]
        kp_text=('2.3. Мощность: 165 кВт\\n2.4. Рабочий объём: 6,0 л\\n'
                 '2.5. Число цилиндров: 6\\n3.1. Срок поставки: 20 календарных дней\\n'
                 'Сведения о Поставщике: опыт поставок — 7 лет, сервисный центр есть, '
                 'в реестре недобросовестных поставщиков отсутствует.')
        numbered=analyze_documents('\\n'.join(tz_lines),[
            ('Предложение ДВС 2026.txt',kp_text)])
        assert numbered['engine']=='numbered-criteria-v1',numbered.get('engine')
        assert len(numbered['requirements'])==18,len(numbered['requirements'])
        statuses={c['id']:c['status'] for c in numbered['suppliers'][0]['checks']}
        assert statuses['2.3']=='pass' and statuses['2.5']=='pass'
        assert statuses['4.3']=='unknown',statuses
        assert numbered['suppliers'][0]['unknown']>=1
        print('KRAKEN 18 NUMBERED TZ CRITERIA SMOKE OK')

if __name__=='__main__':
    run()
