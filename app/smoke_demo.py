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

        # Regression for the five pump files that caused repeated server restarts.
        pump_tz="""Техническое задание

Предмет закупки: насос центробежный промышленный для перекачивания технической воды.
Количество: ровно 4 шт.

Технические характеристики
Мощность двигателя: не менее 5,5 кВт.
Напряжение: 380 В.
Частота: 50 Гц.
Рабочее давление: не менее 6 бар.
Масса: не более 85 кг.
Длина: от 400 до 650 мм.
Степень защиты: IP55.
Материал корпуса: нержавеющая сталь.
Состояние: новое.

Условия поставки
Упаковка: деревянная транспортная тара.
Гарантия: не менее 24 месяцев.
Срок поставки: не более 30 календарных дней.
Цена: не более 600 000 руб. за всю партию с НДС и доставкой до склада заказчика."""
        pump_good="""Коммерческое предложение
Исх. № ВГ-116/26 от 12.11.2026
Поставщик: ООО «ВекторГидро»
Заказчик: ООО «СеверПромВодоснабжение»
Предлагаемая модель: ВГ-55Н

Поставка насосных агрегатов со склада производителя. В комплект входят заводские паспорта и крепёж.

Технические характеристики
Предмет закупки: насос центробежный промышленный для перекачивания технической воды.
Количество: 4 шт.
Мощность двигателя: 5500 Вт.
Напряжение: 380 В.
Частота: 50 Гц.
Рабочее давление: 0,7 МПа.
Вес: 78 кг.
Длина: 55 см.
Степень защиты: IP55.
Материал корпуса: нержавеющая сталь.
Состояние: новое.
Упаковка: деревянная транспортная тара.
Гарантия: 2 года.
Срок поставки: 21 календарный день.
Цена: 480 000 руб. за всю партию с НДС и доставкой до склада заказчика.

Условия оплаты: 30% аванс, 70% после приемки оборудования.
Срок действия предложения: до 15.12.2026.
Документы при поставке: паспорт изделия и универсальный передаточный документ.
Предложение подготовлено отделом продаж."""
        pump_bad=pump_good.replace('ВГ-116/26','АМ-208/26').replace('ВекторГидро','АкваМеханика').replace('ВГ-55Н','АМ-40С').replace('5500 Вт','4 кВт').replace('0,7 МПа','5 бар').replace('IP55','IP54').replace('21 календарный день','35 календарных дней').replace('480 000','396 000')
        pump_unknown=pump_good.replace('ВГ-116/26','ПП-341/26').replace('ВекторГидро','ПромПоток').replace('ВГ-55Н','ПП-60Н').replace('0,7 МПа','6,5 бар').replace('Гарантия: 2 года.\n','').replace('21 календарный день','20 рабочих дней').replace('480 000','452 000').replace('Условия оплаты:', 'Дополнительные данные из приложения к КП:\nРабочее давление: 5 бар.\n\nУсловия оплаты:')
        pump_expensive=pump_good.replace('ВГ-116/26','ГК-097/26').replace('ВекторГидро','ГидроКомплект').replace('ВГ-55Н','ГК-75Н').replace('5500 Вт','7,5 кВт').replace('0,7 МПа','8 бар').replace('4 шт.','3 шт.').replace('78 кг','95 кг').replace('21 календарный день','18 календарных дней').replace('480 000','645 000')
        pump_files=[('tz',('01_ТЗ_СеверПромВодоснабжение.txt',pump_tz.encode(),'text/plain'))]+[
            ('proposals',(name,body.encode(),'text/plain')) for name,body in [
                ('02_КП_ВекторГидро.txt',pump_good),
                ('03_КП_АкваМеханика.txt',pump_bad),
                ('04_КП_ПромПоток.txt',pump_unknown),
                ('05_КП_ГидроКомплект.txt',pump_expensive)]]
        # Deliberately deny E5 the memory it needs: the HTTP job must still
        # complete and retain all compliance results and BM25 citations.
        os.environ['EVIDENCE_RERANKER']='e5'
        os.environ['E5_WEB_WORKER_MEMORY_MB']='64'
        try:
            submitted=client.post('/api/analysis-jobs',files=pump_files,headers={'X-Kraken-Request':'1'})
            assert submitted.status_code==202,submitted.text
            jid=submitted.json()['job_id']
            for _ in range(100):
                response=client.get('/api/analysis-jobs/'+jid,headers={'X-Kraken-Request':'1'})
                if response.json().get('status')!='processing':break
                time.sleep(.1)
            assert response.status_code==200 and response.json()['status']=='complete',response.text
            payload=response.json()
            result=payload['result']
            assert len(result['requirements'])==15,len(result['requirements'])
            got=[(s['passed'],s['failed'],s['unknown']) for s in result['suppliers']]
            assert got==[(15,0,0),(11,4,0),(12,0,3),(12,3,0)],got
            assert result['recommended']=='02_КП_ВекторГидро.txt',result['recommended']
            assert result['evidence_retrieval']['mode']=='bm25',result['evidence_retrieval']['mode']
            for _ in range(30):
                reread=client.get('/api/analyses/'+payload['id'],headers={'X-Kraken-Request':'1'})
                assert reread.status_code==200,reread.text
                if reread.json()['evidence_retrieval'].get('semantic_status')=='fallback':break
                time.sleep(.1)
            final=reread.json()
            assert final['evidence_retrieval']['semantic_status']=='fallback',final['evidence_retrieval']
            assert final['recommended']==result['recommended']
            assert len(final['evidence_retrieval']['results'])==60
            print('KRAKEN 5 PUMP FILES UPLOAD / LOW-MEMORY E5 FALLBACK / 15-0-0 WINNER OK',flush=True)
        finally:
            os.environ['EVIDENCE_RERANKER']='lexical'
            os.environ.pop('E5_WEB_WORKER_MEMORY_MB',None)


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
        kp_text=('2.3. Мощность: 165 кВт\n2.4. Рабочий объём: 6,0 л\n'
                 '2.5. Число цилиндров: 6\n3.1. Срок поставки: 20 календарных дней\n'
                 'Сведения о Поставщике: опыт поставок — 7 лет, сервисный центр есть, '
                 'в реестре недобросовестных поставщиков отсутствует.')
        numbered=analyze_documents('\n'.join(tz_lines),[
            ('Предложение ДВС 2026.txt',kp_text)])
        assert numbered['engine']=='numbered-criteria-v1',numbered.get('engine')
        assert len(numbered['requirements'])==18,len(numbered['requirements'])
        statuses={c['id']:c['status'] for c in numbered['suppliers'][0]['checks']}
        assert statuses['2.3']=='pass' and statuses['2.5']=='pass'
        assert statuses['4.3']=='unknown',statuses
        assert numbered['suppliers'][0]['unknown']>=1
        print('KRAKEN 18 NUMBERED TZ CRITERIA SMOKE OK')

        # The regression that triggered this fix: a real user uploaded a
        # smartwatch TZ in unnumbered "attribute: condition" form, and the
        # old numeric parser exposed only the warranty requirement.
        from .criteria_analysis import analyze_colon
        sample_tz='''Форм-фактор: наручные.
Дисплей: диагональ не менее 1.3 дюйма.
Совместимость с ОС: Android.
Уведомления: мессенджеры.
Датчики здоровья: пульсометр.
Автономность: не менее 5 суток.
Водозащита: IP68 (обязательное совпадение).
Спортивные режимы: не менее 8.
Связь и навигация: Bluetooth.
Гарантия и комплект: гарантия не менее 12 месяцев.
Условия поставки: партия 100 шт., срок не более 30 календарных дней'''
        sample_offer='''Форм-фактор: наручные.
Дисплей: 1.4 дюйма.
Совместимость: Android 6+.
Уведомления: мессенджеры.
Датчики: пульсометр.
Автономность: до 7 суток.
Водозащита: IP68.
Спорт: 10 режимов.
Связь: Bluetooth 5.1.
Поставка: партия 120 штук, срок 27 дней'''
        sample=analyze_colon(sample_tz,[('КП1.txt',sample_offer)])
        assert sample and len(sample['requirements'])==12,sample
        checkmap={c['parameter']:c for c in sample['suppliers'][0]['checks']}
        assert checkmap['Спортивные режимы']['status']=='pass'
        assert checkmap['Автономность']['status']=='unknown'
        assert checkmap['Гарантия и комплект']['status']=='unknown'
        assert checkmap['Водозащита']['status']=='pass'
        assert sample['suppliers'][0]['passed']==10,sample['suppliers'][0]
        print('KRAKEN SMARTWATCH 12 ATOMIC CRITERIA SMOKE OK')
        four_offers=[
            ('КП1.txt',sample_offer),
            ('КП2.txt',"""Форм-фактор: наручные, TPU-ремешок.
Дисплей: 1.3 дюйма.
Совместимость: Android 6+.
Уведомления: телефон.
Датчики: пульсометр.
Автономность: до 6 суток.
Водозащита: IP67.
Спорт: 12 режимов.
Связь: Bluetooth 5.2.
Поставка: 70 штук, срок 39 дней"""),
            ('КП3.txt',"""Форм-фактор: наручные, нейлоновый ремешок.
Дисплей: 1.39 дюйма.
Совместимость: Android 6+.
Уведомления: мессенджеры.
Датчики: сердцедатчик.
Автономность: до 10 суток.
Водозащита: IP68.
Спорт: 15 режимов.
Связь: Bluetooth 5.2.
Поставка: 70 штук, срок 23 дня"""),
            ('КП4.txt',"""Форм-фактор: наручные, кожаный ремешок.
Дисплей: 1.32 дюйма.
Совместимость: Android 7+.
Уведомления: Мессенджеры.
Датчики: пульсометр.
Автономность: до 3 суток.
Водозащита: 5 ATM
Спорт: 2 режима.
Связь: Bluetooth 5.2.
Поставка: партия 750 штук, 8 дней"""),
        ]
        comparison=analyze_documents(sample_tz,four_offers)
        assert comparison['engine']=='colon-criteria-v1',comparison['engine']
        assert len(comparison['requirements'])==12
        assert len(comparison['suppliers'])==4
        statuses=[(x['passed'],x['failed'],x['unknown']) for x in comparison['suppliers']]
        assert statuses==[(10,0,2),(6,3,3),(9,1,2),(8,2,2)],statuses
        assert all(len(x['checks'])==12 for x in comparison['suppliers'])
        print('KRAKEN ALL FOUR SMARTWATCH KP CRITERIA COMPARISON OK')
        # "до N суток" describes an upper bound, NOT a guaranteed minimum.
        from .criteria_analysis import evaluate
        battery_req={'key':'battery','body':'не менее 5 суток'}
        for value in (6,7,10):
            status,reason,needed,actual,unit=evaluate(
                battery_req,f'Автономность: до {value} суток')
            assert status=='unknown' and 'максимум' in reason.lower()
            assert actual==value and needed==5
        status,reason,*_=evaluate(battery_req,'Автономность: до 3 суток')
        assert status=='fail' and '3' in reason and '5' in reason
        status,reason,*_=evaluate(battery_req,'Автономность: не менее 7 суток')
        assert status=='pass', (status,reason)
        status,reason,*_=evaluate(battery_req,'Автономность: не менее 3 суток')
        assert status=='unknown', (status,reason)
        print('KRAKEN BATTERY BOUNDS INTERPRETATION SMOKE OK')

        from .local_criteria import analyze_local, numeric, relation
        # The same dimensional unit is NOT proof of the same parameter.
        cases=[
            ('Мощность не менее 5 кВт','Мощность 5500 Вт','pass'),
            ('Мощность не менее 5 кВт','Мощность 4 кВт','fail'),
            ('Мощность не менее 5 кВт','Напряжение 5 В','unknown'),
            ('Автономность: не менее 5 суток','Время работы: 120 часов','pass'),
            ('Автономность: не менее 5 суток','Срок поставки: 7 дней','unknown'),
            ('Автономность: не менее 5 суток','Автономность: до 7 суток','unknown'),
            ('Автономность: не менее 5 суток','Автономность: до 3 суток','fail'),
            ('Автономность: не менее 5 суток','Автономность: от 5 до 8 суток','pass'),
            ('Длина: от 10 до 20 см','Длина: 150 мм','pass'),
            ('Длина: от 10 до 20 см','Длина: 25 см','fail'),
            ('Длина: от 10 до 20 см','Длина: от 15 до 25 см','unknown'),
            ('Масса: не более 2 кг','Вес: 1800 г','pass'),
            ('Гарантия: не менее 24 месяцев','Гарантия: 2 года','pass'),
            ('Срок поставки: не более 30 календарных дней','Срок доставки: 25 рабочих дней','unknown'),
            ('Срок поставки: не более 30 дней','Срок поставки: до 25 дней','pass'),
            ('Количество: ровно 100 шт.','Количество: 120 шт.','fail'),
            ('Давление: не менее 2 бар','Давление: 250 кПа','pass'),
            ('Давление: не менее 2 бар','Давление: 200 В','unknown'),
            ('Мощность: не менее 5 кВт','Мощность: 6 кВт\nМощность: 4 кВт','unknown'),
            ('Номинальная мощность: не менее 5 кВт','Максимальная мощность: 10 кВт','unknown'),
            ('Совместимость с ОС: Android 6+','Совместимость: Android 7+','fail'),
            ('Совместимость с ОС: Android','Совместимость: не поддерживает Android','fail'),
            ('Водозащита: IP68','Водозащита: IP67','fail'),
            ('Водозащита: IP68','Водозащита: 5 ATM','unknown'),
            ('Толщина: не менее 2 мм','Толщина: 3 мм','pass'),
            ('Толщина: не менее 2 мм','Ширина: 3 мм','unknown'),
            ('Мощность: 5 кВт или 10 кВт','Мощность: 5 кВт','unknown'),
            ('Мощность: 5 кВт ± 10%','Мощность: 5 кВт','pass'),
            ('Масса: менее 2 кг','Вес: 2 кг','fail'),
            ('Масса: более 2 кг','Вес: 2 кг','fail'),
            ('Мощность: не менее 5 кВт','Мощность: от 3 до 8 кВт','unknown'),
            ('Мощность: 5 кВт ± 10%','Мощность: 5.6 кВт','fail'),
            ('Длина: 10 ± 1 см','Длина: 105 мм','pass'),
            ('Количество: 100 шт.','Количество: 120 шт.','fail'),
            ('Масса: не должна превышать 2 кг','Вес: 1.8 кг','pass'),
            ('Масса: не превышает 2 кг','Вес: 1.8 кг','pass'),
            ('Совместимость: Android','Совместимость: Android, без iOS','pass'),
            ('Связь: Bluetooth','Связь: Bluetooth, без проводов','pass'),
            ('Дисплей: 1.3 дюйма','Дисплей: 33.02 мм','pass'),
            ('Автономность: от 5 до 8 суток','Автономность: от 120 до 168 часов','pass'),
        ]
        for req,kp,expected in cases:
            local=analyze_documents(req,[('offer.txt',kp)])
            actual=local['suppliers'][0]['checks'][0]['status']
            assert actual==expected,(req,kp,expected,local)
        prose=analyze_documents(
            'Устройство должно иметь дисплей не менее 1.3 дюйма и работать без подзарядки минимум 5 суток.',
            [('offer.txt','Дисплей: 1.4 дюйма\nАвтономность: 120 часов')])
        assert len(prose['requirements'])==2,prose
        assert prose['suppliers'][0]['passed']==2,prose
        table=analyze_documents('Параметр | Требование\nМасса | не более 2 кг\nМощность | не менее 5 кВт',
             [('offer.txt','Параметр | Значение\nВес | 1800 г\nМощность | 6000 Вт')])
        assert len(table['requirements'])==2 and table['suppliers'][0]['passed']==2,table
        unknown=analyze_documents('Необходимо обеспечить особую технологию защиты.',
                                  [('offer.txt','Качественный товар')])
        assert len(unknown['requirements'])==1 and unknown['suppliers'][0]['unknown']==1,unknown
        # Verify that semantic candidates cannot hide a contradiction elsewhere.
        from .local_criteria import annotate_evidence
        tz='Мощность: не менее 5 кВт'
        kp='Мощность: 6 кВт\nМощность: 4 кВт\nНапряжение: 5 В'
        retrieval={'results':[{'supplier':'offer.txt','section':'local-1','fragments':[
            {'line':1,'quote':'Мощность: 6 кВт','relevance_score':.99},
            {'line':3,'quote':'Напряжение: 5 В','relevance_score':.98}]}]}
        annotated=annotate_evidence(tz,[('offer.txt',kp)],retrieval)
        fragments=annotated['results'][0]['fragments']
        assert fragments[0]['parameter_match']=='confirmed' and fragments[0]['verification_status']=='pass',fragments
        assert fragments[1]['parameter_match']=='unconfirmed' and fragments[1]['verification_status']=='unknown',fragments
        refined=analyze_local(tz,[('offer.txt',kp)],annotated)
        assert refined['suppliers'][0]['checks'][0]['status']=='unknown',refined
        span=analyze_documents('Автономность: от 5 до 8 суток',
            [('offer.txt','Автономность: от 120 до 168 часов')])['suppliers'][0]['checks'][0]
        assert span['required']==5 and span['upper']==8 and span['actual']=='5–7',span
        generic_numbered=analyze_documents('1.1. Мощность: не более 5 кВт\n1.2. Масса: не более 2 кг\n1.3. Автономность: не менее 5 суток',
            [('offer.txt','Мощность: 6 кВт\nМасса: 1800 г\nАвтономность: 120 часов')])
        assert generic_numbered['engine']=='colon-criteria-v1',generic_numbered
        assert [c['status'] for c in generic_numbered['suppliers'][0]['checks']]==['fail','pass','pass'],generic_numbered
        changed_laptop=analyze_documents('3.2 | Процессор | Не менее 8 ядер, базовая частота не ниже 2,0 ГГц | Обязательно\n3.3 | Оперативная память | Не менее 32 ГБ | Обязательно',
             [('offer.txt','Процессор: 6 ядер, 2 ГГц\nОперативная память: 16 ГБ')])
        assert changed_laptop['engine']!='requirements-v2',changed_laptop
        assert changed_laptop['suppliers'][0]['checks'][-1]['status']=='fail',changed_laptop
        print('KRAKEN LOCAL CRITERIA 45+ CASES AND CANDIDATE VERIFICATION SMOKE OK')

if __name__=='__main__':
    run()
