"""Regression for the real four smartwatch КП and unnumbered ТЗ structure."""
from app.analysis import analyze_documents
from app.ranking import build_ranking
from app.full_report import build_full_report

TZ="""Форм-фактор: наручные.
Дисплей: диагональ не менее 1.3 дюйма.
Совместимость с ОС: Android.
Уведомления: мессенджеры.
Датчики здоровья: пульсометр.
Автономность: не менее 5 суток.
Водозащита: IP68 (обязательное совпадение с КП-1 и КП-3).
Спортивные режимы: не менее 8.
Связь и навигация: Bluetooth.
Гарантия и комплект: гарантия не менее 12 месяцев.
Условия поставки: партия 100 шт., срок не более 30 календарных дней"""

COMMON="""Форм-фактор: наручные.
Совместимость: Android 6+.
Уведомления: мессенджеры.
Датчики: пульсометр.
Связь: Bluetooth 5.1."""
OFFERS={
'КП1.txt':COMMON+"\nДисплей: 1.4 дюйма.\nАвтономность: до 7 суток.\nВодозащита: IP68.\nСпорт: 10 режимов.\nПоставка: партия 120 штук, срок 27 дней",
'КП2.txt':"""Форм-фактор: наручные, TPU-ремешок.
Дисплей: 1.3 дюйма.
Совместимость: Android 6+.
Уведомления: телефон.
Датчики: пульсометр.
Автономность: до 6 суток.
Водозащита: IP67.
Спорт: 12 режимов.
Связь: Bluetooth 5.2.
Поставка: 70 штук, срок 39 дней""",
'КП3.txt':"""Форм-фактор: наручные, нейлоновый ремешок.
Дисплей: 1.39 дюйма.
Совместимость: Android 6+.
Уведомления: мессенджеры.
Датчики: сердцедатчик.
Автономность: до 10 суток.
Водозащита: IP68.
Спорт: 15 режимов.
Связь: Bluetooth 5.2.
Поставка: 70 штук, срок 23 дня""",
'КП4.txt':"""Форм-фактор: наручные, кожаный ремешок.
Дисплей: 1.32 дюйма.
Совместимость: Android 7+.
Уведомления: Мессенджеры.
Датчики: пульсометр.
Автономность: до 3 суток.
Водозащита: 5 ATM
Спорт: 2 режима.
Связь: Bluetooth 5.2.
Поставка: партия 750 штук, 8 дней"""
}

def test_all_12_atomic_requirements_are_preserved():
    result=analyze_documents(TZ,list(OFFERS.items()))
    assert result['engine']=='colon-criteria-v1'
    assert len(result['requirements'])==12
    assert len(result['suppliers'])==4
    results={s['name']:s for s in result['suppliers']}
    assert [(results[k]['passed'],results[k]['failed'],results[k]['unknown'])
            for k in OFFERS]==[(10,0,2),(6,3,3),(9,1,2),(8,2,2)]
    assert all(len(s['checks'])==12 for s in results.values())
    assert all(c['requirement_locator'] and c['requirement_source']
               for s in results.values() for c in s['checks'])
    assert all(c['offer_locator'] for s in results.values()
               for c in s['checks'] if c.get('offer_source'))
    assert result['recommended'] is None
    rank=build_ranking(result)
    assert not rank['ranked'] and not rank['recommended']
    result['ranking']=rank
    report=build_full_report(result)
    assert report['total']==4 and report['eligible']==0
    assert report['rejected']==3 and report['review']==1

def test_ambiguous_battery_and_missing_warranty_are_not_passes():
    result=analyze_documents(TZ,list(OFFERS.items()))
    for supplier in result['suppliers']:
        checks={c['parameter']:c for c in supplier['checks']}
        assert checks['Гарантия и комплект']['status']=='unknown'
        assert checks['Автономность']['status']!='pass'
    kp4=result['suppliers'][3]
    assert next(c for c in kp4['checks'] if c['parameter']=='Водозащита')['status']=='unknown'
    assert next(c for c in kp4['checks'] if c['parameter']=='Спортивные режимы')['status']=='fail'

def test_unknown_labels_do_not_disappear():
    text=TZ+"\nОсобое условие: специальная технология защиты."
    result=analyze_documents(text,[('КП.txt',OFFERS['КП1.txt'])])
    assert len(result['requirements'])==13
    assert result['suppliers'][0]['checks'][-1]['status']=='unknown'
