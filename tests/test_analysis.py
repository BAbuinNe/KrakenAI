from app.analysis import analyze_documents

def test_comparison():
    result=analyze_documents('Мощность не менее 5 кВт\nЦена не более 100000 руб\nГарантия от 24 мес',[
        ('A.pdf','Мощность 5500 Вт\nЦена 92000 руб\nГарантия 2 года'),
        ('B.pdf','Мощность 4 кВт\nЦена 85000 руб\nГарантия 12 мес')])
    assert result['recommended']=='A.pdf'
    assert result['suppliers'][0]['passed']==3
    assert result['suppliers'][1]['failed']==2

def test_missing_is_unknown_not_fail():
    result=analyze_documents('Мощность не менее 5 кВт',[('A.pdf','Цена 50000 руб')])
    assert result['recommended'] is None
    assert result['suppliers'][0]['unknown']==1

def test_no_requirements_is_explicit():
    result=analyze_documents('Обеспечить надлежащее качество',[('A.pdf','Хороший товар')])
    assert result['recommended'] is None
    assert result['warning']
