from app.analysis import analyze_documents

TZ = """Техническое задание на выбор ноутбука
3.1 | Экран | Диагональ 14–15,6", разрешение не ниже 1920×1080, матовое покрытие | Обязательно
3.2 | Процессор | Не менее 6 ядер, базовая частота не ниже 2,0 ГГц | Обязательно
3.3 | Оперативная память | Не менее 16 ГБ, возможность расширения до 32 ГБ | Обязательно
3.4 | Накопитель | SSD не менее 512 ГБ, интерфейс NVMe | Обязательно
3.5 | Аккумулятор | Ёмкость не менее 50 Вт·ч, автономность не менее 8 часов | Обязательно
3.6 | Вес | Не более 1,8 кг | Обязательно
3.7 | Порты | Не менее 2×USB-A, 1×USB-C (с поддержкой зарядки), HDMI | Обязательно
3.8 | Связь | Wi-Fi 6, Bluetooth 5.0 и выше | Обязательно
3.9 | Веб-камера | Не менее 720p, встроенный микрофон | Обязательно
3.10 | Клавиатура | Полноразмерная, с подсветкой | Желательно
3.11 | Сканер отпечатков пальцев | Наличие | Желательно
3.12 | ОС | Windows 11 Pro | Обязательно
4.4 | Корпус | Металлический корпус | 5%
"""
OFFER = """Ноутбук «AeroLite 14»
Описание: Тонкий и лёгкий ноутбук. Корпус из алюминиевого сплава, подсветка клавиатуры, быстрая зарядка.
Экран: 14 дюймов, IPS, 1920×1080
Процессор: 4 ядра, 2,4 ГГц (турбо до 3,8 ГГц)
Оперативная память: 8 ГБ
Накопитель SSD: 256 ГБ
Аккумулятор: 42 Вт·ч
Вес: 1,2 кг
Порты: 2×USB-C, 1×USB-A, HDMI
"""

def test_structured_tz_detects_five_explicit_mismatches():
    result = analyze_documents(TZ, [('Noutbuk.docx', OFFER)])
    supplier = result['suppliers'][0]
    assert result['engine'] == 'requirements-v2'
    assert supplier['mandatory_failed'] == 5
    assert result['recommended'] is None
    failures = {c['parameter'] for c in supplier['checks'] if c['status'] == 'fail' and c['mandatory']}
    assert failures == {'Ядра процессора','Оперативная память','Объём SSD','Ёмкость аккумулятора','Количество USB-A'}

def test_missing_values_are_unknown_not_false_failures():
    result = analyze_documents(TZ, [('empty.docx','Ноутбук без подробных характеристик')])
    supplier = result['suppliers'][0]
    assert supplier['mandatory_failed'] == 0
    assert supplier['mandatory_unknown'] > 0
    assert result['recommended'] is None

def test_old_industrial_numeric_analysis_still_works():
    result = analyze_documents('Мощность не менее 5 кВт', [('a.txt','Мощность 6 кВт')])
    assert result['engine'] == 'local-criteria-v2'
    assert result['suppliers'][0]['passed'] == 1
