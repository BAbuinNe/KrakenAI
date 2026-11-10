from app.price_extraction import extract_rub_price
from app.analysis import analyze_documents

def test_price_formats():
    examples = {
        'Цена: 85 000 руб.':85000,
        'Стоимость товара: 85000 ₽':85000,
        'Итого: ₽85 000':85000,
        'Цена 85 тыс. руб.':85000,
        'Стоимость: 85 000,50 руб.':85000.50,
        'Итоговая стоимость | 85 000 | руб':85000,
        'Итого: 0,085 млн руб.':85000,
    }
    for source,expected in examples.items():
        price,evidence,state=extract_rub_price(source)
        assert state=='found',source
        assert price==expected,(source,price)
        assert evidence==source

def test_ambiguous_and_foreign_price_are_not_assumed():
    for source in ('Цена 85 000 USD','Цена 84 000 руб.\nЦена 89 000 руб.',
                   'Стоимость не указана'):
        assert extract_rub_price(source)[0] is None

def test_total_price_wins_over_unit_price():
    price,_,status=extract_rub_price('Цена за штуку: 500 руб\nИтого: 85 000 руб')
    assert price==85000 and status=='found'

def test_laptop_price_reaches_ranking_facts():
    tz='''3.2 | Процессор | Не менее 6 ядер | Обязательно
4.10 | Цена | В пределах бюджета 90 000 руб | 25%'''
    result=analyze_documents(tz,[('A.docx','Процессор: 6 ядер\nЦена: 85 тыс. руб.')])
    supplier=result['suppliers'][0]
    assert supplier['price']==85000
    assert any(x['key']=='price' and x['value']==85000 for x in supplier['facts'])
    price_check=next(c for c in supplier['checks'] if c['section']=='4.10')
    assert price_check['status']=='pass'
    assert price_check['actual']==85000

def test_generic_price_recognition():
    result=analyze_documents('Цена не более 90 000 руб', [('A.docx','Стоимость: ₽85 000')])
    assert result['engine']=='rules-v1'
    assert result['suppliers'][0]['checks'][0]['status']=='pass'
