"""Evidence-based laptop specification comparison for structured technical requirements.

Each atomic check cites the original requirement and the proposal line.
Missing facts are unknown, not failures or matches.
"""
from __future__ import annotations
import re
from typing import Any
from .price_extraction import extract_rub_price

def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]

def _find(text: str, pattern: str) -> str | None:
    for line in _lines(text):
        if re.search(pattern, line, flags=re.I):
            return line
    return None

def _num(text: str, pattern: str) -> float | None:
    m = re.search(pattern, text, re.I)
    return float(m.group(1).replace(',', '.')) if m else None

def _loc(text: str, source: str | None) -> dict[str, Any] | None:
    if not source: return None
    for i, line in enumerate(text.splitlines(), 1):
        if line.strip() == source.strip():
            return {'kind': 'line', 'value': i}
    return None

def _extract_tz_rows(text: str) -> list[tuple[str,str,str,str]]:
    rows = []
    for line in _lines(text):
        parts = [p.strip() for p in line.split('|')]
        if len(parts) >= 4 and re.fullmatch(r'3\.\d+|4\.\d+', parts[0]):
            rows.append((parts[0], parts[1], ' '.join(parts[2:-1]), parts[-1]))
    return rows

def _value_for(key: str, text: str) -> tuple[float | str | None, str | None]:
    if key == 'price':
        amount, evidence, _ = extract_rub_price(text)
        return amount, evidence
    rules: dict[str,tuple[str,str]] = {
       'screen_inches': (r'(?:экран|дисплей).*?(\d+(?:[.,]\d+)?)\s*(?:дюйм|["″])', r'(?:экран|дисплей)'),
       'screen_width': (r'(\d{3,4})\s*[xх×]\s*(\d{3,4})', r'(?:экран|дисплей|разрешени)'),
       'cpu_cores': (r'(\d+)\s*яд(?:ер|ра|ро)', r'процессор|яд(?:ер|ра|ро)'),
       'cpu_base': (r'(\d+(?:[.,]\d+)?)\s*ггц', r'процессор'),
       'ram': (r'(\d+(?:[.,]\d+)?)\s*гб', r'оперативн|\bозу\b|\bram\b'),
       'ssd': (r'(\d+(?:[.,]\d+)?)\s*(?:гб|тб)', r'накопител|\bssd\b'),
       'battery_wh': (r'(\d+(?:[.,]\d+)?)\s*вт\s*[·*\-]?\s*ч', r'аккумулятор|батаре|ёмкост'),
       'battery_hours': (r'(\d+(?:[.,]\d+)?)\s*час', r'автоном|время работы'),
       'weight': (r'(\d+(?:[.,]\d+)?)\s*кг', r'вес|масса'),
       'usb_a': (r'(\d+)\s*[×xх]?\s*usb[\s\-]*a', r'порт|usb'),
       'usb_c': (r'(\d+)\s*[×xх]?\s*usb[\s\-]*c', r'порт|usb'),
       'wifi': (r'wi[\s\-]*fi\s*(\d+)', r'wi[\s\-]*fi'),
       'bluetooth': (r'bluetooth\s*(\d+(?:[.,]\d+)?)', r'bluetooth'),
       'camera': (r'(\d{3,4})\s*p\b', r'веб.?камер|камер'),
       'brightness': (r'(\d+)\s*нит', r'яркост|экран'),
       'srgb': (r'(\d+)\s*%.*?srgb|srgb.*?(\d+)\s*%', r'srgb|охват'),
       'tdp': (r'(\d+)\s*вт', r'\btdp\b|теплопакет'),
       'warranty': (r'(\d+)\s*(?:лет|года|год)', r'гарант'),
       'price': (r'(\d[\d\s]*)\s*(?:руб|₽)', r'цен|стоимост'),
    }
    boolean: dict[str,str] = {
        'matte': r'матов|антиблик',
        'ram_upgrade': r'расширен|до\s*32\s*гб|слот\s*озу',
        'nvme': r'\bnvme\b',
        'usb_c_charging': r'usb[\s\-]*c.{0,55}заряд|заряд.{0,55}usb[\s\-]*c|power delivery',
        'hdmi': r'\bhdmi\b',
        'microphone': r'микрофон',
        'keyboard_backlight': r'подсветк.{0,25}клавиатур|клавиатур.{0,25}подсветк',
        'full_keyboard': r'полноразмерн.{0,20}клавиатур',
        'fingerprint': r'отпечатк|сканер пальц',
        'os': r'windows\s*11\s*pro|корпоративн.{0,25}лицензи',
        'metal': r'алюмини|металлическ|усиленн.{0,20}корпус',
        'fast_charge': r'быстр.{0,15}заряд',
        'service': r'выездн.{0,20}обслуживан',
        'thunderbolt': r'thunderbolt\s*4',
        'tpm': r'tpm\s*2[.,]0',
        'shutter': r'шторк.{0,20}камер|камер.{0,20}шторк',
        'hinge': r'180\s*°|180\s*градус'
    }
    if key in boolean:
        src = _find(text, boolean[key])
        return (True,src) if src else (None,None)
    if key not in rules: return None,None
    pattern, label = rules[key]
    for src in _lines(text):
        if not re.search(label,src,re.I):continue
        m = re.search(pattern,src,re.I)
        if not m:continue
        try:
            raw = next(g for g in m.groups() if g is not None)
            val = float(raw.replace(' ','').replace(',','.'))
            if key == 'ssd' and re.search(r'\d+(?:[.,]\d+)?\s*тб',src,re.I): val *= 1024
            return val,src
        except (StopIteration,ValueError):continue
    return None,None

# Requirement clause -> atomic checks; compound clauses are always split.
SPECS = {
 '3.1': [('screen_inches','Диагональ экрана','range',14,15.6,'″'),('screen_width','Разрешение экрана (ширина)','min',1920,None,'px'),('matte','Матовое покрытие','yes',True,None,'')],
 '3.2': [('cpu_cores','Ядра процессора','min',6,None,'шт.'),('cpu_base','Базовая частота процессора','min',2,None,'ГГц')],
 '3.3': [('ram','Оперативная память','min',16,None,'ГБ'),('ram_upgrade','Возможность расширения ОЗУ до 32 ГБ','yes',True,None,'')],
 '3.4': [('ssd','Объём SSD','min',512,None,'ГБ'),('nvme','Интерфейс NVMe','yes',True,None,'')],
 '3.5': [('battery_wh','Ёмкость аккумулятора','min',50,None,'Вт·ч'),('battery_hours','Автономность','min',8,None,'часов')],
 '3.6': [('weight','Вес','max',1.8,None,'кг')],
 '3.7': [('usb_a','Количество USB-A','min',2,None,'шт.'),('usb_c','Количество USB-C','min',1,None,'шт.'),('usb_c_charging','Зарядка через USB-C','yes',True,None,''),('hdmi','Порт HDMI','yes',True,None,'')],
 '3.8': [('wifi','Версия Wi-Fi','min',6,None,''),('bluetooth','Версия Bluetooth','min',5,None,'')],
 '3.9': [('camera','Веб-камера','min',720,None,'p'),('microphone','Встроенный микрофон','yes',True,None,'')],
 '3.10':[('full_keyboard','Полноразмерная клавиатура','yes',True,None,''),('keyboard_backlight','Подсветка клавиатуры','yes',True,None,'')],
 '3.11':[('fingerprint','Сканер отпечатков','yes',True,None,'')],
 '3.12':[('os','Windows 11 Pro / совместимая корпоративная лицензия','yes',True,None,'')],
 '4.1':[('brightness','Яркость экрана','min',300,None,'нит'),('srgb','Охват sRGB','min',90,None,'%')],
 '4.2':[('fast_charge','Быстрая зарядка (50% за 30 мин)','yes',True,None,'')],
 '4.3':[('tdp','Энергопотребление CPU (TDP)','max',28,None,'Вт')],
 '4.4':[('metal','Металлический / усиленный корпус','yes',True,None,'')],
 '4.5':[('warranty','Гарантийный срок','min',3,None,'лет'),('service','Выездное обслуживание','yes',True,None,'')],
 '4.6':[('weight','Вес по дополнительному критерию','lt',1.4,None,'кг')],
 '4.7':[('thunderbolt','Thunderbolt 4','yes',True,None,'')],
 '4.8':[('tpm','TPM 2.0','yes',True,None,''),('shutter','Шторка веб-камеры','yes',True,None,'')],
 '4.9':[('hinge','Раскрытие 180°','yes',True,None,''),('matte','Антибликовое покрытие','yes',True,None,'')],
 '4.10':[('price','Цена в пределах бюджета','max',90000,None,'руб')],
}
def compare_laptop(tz_text: str, proposals:list[tuple[str,str]]) -> dict[str,Any] | None:
    rows=_extract_tz_rows(tz_text)
    # Avoid applying notebook-specific rules to unrelated technical assignments.
    if not any(n=='3.2' and re.search('процессор', title,re.I) for n,title,_,_ in rows):return None
    # This historical template has fixed thresholds. Never apply them to an
    # unfamiliar table merely because it has the same section numbers.
    for number,title,clause,priority in rows:
        if number not in SPECS:return None
        raw=clause.casefold().replace(',','.')
        values={float(x) for x in re.findall(r'\d+(?:\.\d+)?',raw)}
        for key,label,operator,limit,upper,unit in SPECS[number]:
            if isinstance(limit,(int,float)) and not isinstance(limit,bool) and limit not in values:return None
            if upper is not None and upper not in values:return None
        if number=='3.2' and not (re.search(r'не менее\s+6\s+яд',raw) and re.search(r'не ниже\s+2(?:\.0)?\s*ггц',raw)):return None
        if number=='3.3' and 32 not in values:return None
        if number=='3.12' and 'windows 11 pro' not in raw:return None
    requirements=[]
    for number,title,clause,priority in rows:
        if number not in SPECS:continue
        mandatory = number.startswith('3.') and bool(re.search('обязательн',priority,re.I))
        optional = not mandatory
        for key,label,operator,limit,upper,unit in SPECS[number]:
            requirements.append({'key':key,'parameter':label,'operator':operator,
                'value':limit,'upper':upper,'unit':unit,'source':f'{number} | {title} | {clause} | {priority}',
                'line': next((i for i,l in enumerate(tz_text.splitlines(),1) if l.strip().startswith(number+' |')),0),
                'mandatory':mandatory,'section':number,'optional':optional,
                'weight': float(priority.replace('%','').replace(',','.')) if number.startswith('4.') and priority.replace('%','').strip().isdigit() else None})
    suppliers=[]
    for name,text in proposals:
        checks=[]
        for req in requirements:
            actual, evidence=_value_for(req['key'],text)
            if actual is None:
                status='unknown'; reason='Характеристика не указана в КП — необходимо подтверждение'
            else:
                op=req['operator']; target=req['value']
                valid=(actual>=target if op=='min' else actual<=target if op=='max' else
                       actual<target if op=='lt' else target<=actual<=req['upper'] if op=='range' else bool(actual))
                status='pass' if valid else 'fail'
                reason='Требование подтверждено' if valid else 'Подтверждено несоответствие указанному требованию'
            checks.append({'parameter':req['parameter'],'required':req['value'],
                'actual':actual,'unit':req['unit'],'operator':req['operator'],
                'status':status,'reason':reason,'mandatory':req['mandatory'],
                'section':req['section'],'requirement_source':req['source'],'offer_source':evidence,
                'requirement_locator':_loc(tz_text,req['source']),
                'offer_locator':_loc(text,evidence)})
        mandatory_checks=[c for c in checks if c['mandatory']]
        failed_mandatory=sum(c['status']=='fail' for c in mandatory_checks)
        unknown_mandatory=sum(c['status']=='unknown' for c in mandatory_checks)
        passed_mandatory=sum(c['status']=='pass' for c in mandatory_checks)
        price,price_source,price_status=extract_rub_price(text)
        suppliers.append({'name':name[:100],'checks':checks,
            'passed':sum(c['status']=='pass' for c in checks),
            'failed':sum(c['status']=='fail' for c in checks),
            'unknown':sum(c['status']=='unknown' for c in checks),
            'mandatory_passed':passed_mandatory,'mandatory_failed':failed_mandatory,
            'mandatory_unknown':unknown_mandatory,
            'eligibility':'rejected' if failed_mandatory else 'needs_review' if unknown_mandatory else 'eligible',
            'coverage_percent':round(passed_mandatory/len(mandatory_checks)*100) if mandatory_checks else 0,
            'facts':([{'key':'price','parameter':'Цена','value':price,'unit':'₽',
                       'source':price_source}] if price is not None else []),
            'price':price,'price_source':price_source,'price_status':price_status})
    # Explicit mandatory failure always disqualifies; do not recommend with missing mandatory facts.
    eligible=[s for s in suppliers if s['eligibility']=='eligible']
    recommended=eligible[0]['name'] if len(eligible)==1 else None
    return {'requirements':requirements,'suppliers':suppliers,'recommended':recommended,
        'warning':'Обнаружены нарушения обязательных требований: предложение не допускается к итоговой оценке.' if any(s['mandatory_failed'] for s in suppliers) else
          'Для окончательного выбора проверьте неизвестные обязательные характеристики и оценочные критерии.',
        'engine':'requirements-v2','method':'Проверка каждого атомарного критерия по документальному доказательству'}
