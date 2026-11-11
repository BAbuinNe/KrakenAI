"""Deterministic, explainable first-pass supplier proposal analyzer.

This does NOT claim semantic LLM equivalence. Unsupported clauses remain unverified.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import re
from typing import Any
from .price_extraction import extract_rub_price

NUMBER = r"\d[\d\s\u00a0]*(?:[.,]\d+)?"
UNIT_RE = re.compile(r"(?P<number>" + NUMBER + r")\s*(?P<unit>квт|киловатт(?:а|ов)?|вт|ватт(?:а|ов)?|мвт|в|вольт(?:а|ов)?|кв|кг|г|бар|мпа|па|руб(?:лей|ля|\.)?|₽|тыс\.?\s*руб(?:лей|ля|\.)?|млн\.?\s*руб(?:лей|ля|\.)?|дн(?:я|ей|ь)?|сут(?:ок|ки)?|недел(?:я|и|ь)?|мес(?:яц(?:а|ев)?)?\.?|год(?:а|ов)?|лет|шт\.?|%)(?!\w)", re.I)
FIELDS = {
    'power': ('Мощность', ['мощност'], 'кВт'),
    'voltage': ('Напряжение', ['напряжени'], 'В'),
    'pressure': ('Давление', ['давлени'], 'бар'),
    'mass': ('Масса', ['масса', 'массу', 'вес'], 'кг'),
    'price': ('Цена', ['цен', 'стоимост', 'бюджет'], '₽'),
    'delivery': ('Срок поставки', ['срок поставк', 'доставк'], 'дн.'),
    'warranty': ('Гарантия', ['гаранти'], 'мес.'),
    'quantity': ('Количество', ['количеств', 'штук'], 'шт.'),
}
UNIT_TO_FIELD = {
    'квт': ('power', 1), 'киловатт': ('power', 1), 'вт': ('power', .001), 'ватт': ('power', .001), 'мвт': ('power', 1000),
    'в': ('voltage', 1), 'вольт': ('voltage', 1), 'кв': ('voltage', 1000),
    'бар': ('pressure', 1), 'мпа': ('pressure', 10), 'па': ('pressure', 0.00001),
    'кг': ('mass', 1), 'г': ('mass', .001),
    'руб': ('price', 1), '₽': ('price', 1), 'тысруб': ('price', 1000), 'млнруб': ('price', 1_000_000),
    'дн': ('delivery', 1), 'сут': ('delivery', 1), 'недел': ('delivery', 7),
    'мес': ('warranty', 1), 'год': ('warranty', 12), 'лет': ('warranty', 12),
    'шт': ('quantity', 1)
}

def _unit(s: str) -> tuple[str, float] | None:
    s = re.sub(r'\s+', '', s.lower().replace('.', ''))
    for needle, result in sorted(UNIT_TO_FIELD.items(), key=lambda pair: -len(pair[0])):
        if s.startswith(needle): return result
    return None

def _field_for(line: str) -> str | None:
    lower = line.lower()
    for k, (_label, aliases, _unit_label) in FIELDS.items():
        if any(v in lower for v in aliases): return k
    return None

def _number(raw: str) -> float:
    # Both decimal-comma and decimal-point are supported, grouping whitespace only.
    return float(raw.replace(' ', '').replace('\u00a0','').replace(',', '.'))

def _operator(line: str) -> str:
    l = line.lower()
    if any(p in l for p in ('не менее', 'не ниже', 'от ', 'минимум', 'не меньше', '>=', '≥')): return 'min'
    if any(p in l for p in ('не более', 'не выше', 'до ', 'максимум', 'не больше', '<=', '≤')): return 'max'
    return 'eq'

def _items(text: str, requirement: bool) -> list[dict[str, Any]]:
    items=[]
    seen=set()
    for i, line in enumerate(text.splitlines()):
        line=line.strip()[:400]
        if not line: continue
        suggested=_field_for(line)
        if not suggested: continue
        for match in UNIT_RE.finditer(line):
            unit=_unit(match.group('unit'))
            if not unit or unit[0] != suggested: continue
            try: value=round(_number(match.group('number'))*unit[1], 6)
            except ValueError: continue
            if not (0<=value<=1e12): continue
            # Multiple values on the same line can express ranges: require human review.
            if suggested in seen: continue
            seen.add(suggested)
            items.append({'key': suggested, 'parameter': FIELDS[suggested][0], 'operator':_operator(line) if requirement else 'eq',
                          'value': value, 'unit':FIELDS[suggested][2], 'source':line[:260], 'line':i+1})
            break
    # Price can be written as "₽85 000", "85 тыс. руб." or in a Word table.
    # Do not accidentally treat amounts without verified RUB currency as rubles.
    if not requirement:
        price,source,status=extract_rub_price(text)
        if status=='found':
            line=next((i for i,part in enumerate(text.splitlines(),1)
                       if part.strip()==source.strip()),1)
            items=[item for item in items if item['key']!='price']
            items.append({'key':'price','parameter':'Цена','operator':'eq',
                          'value':price,'unit':'₽','source':source,'line':line})
    return items

def _source_locator(text: str, at_line: int) -> dict[str, Any]:
    """Identify parsed page/sheet marker without guessing a source location."""
    page = None
    sheet = None
    for line in text.splitlines()[:at_line]:
        marker = re.match(r'^Страница\s+(\d+):\s*$', line.strip(), re.I)
        if marker:
            page = int(marker.group(1))
            sheet = None
        elif line.lstrip().startswith('Лист: '):
            sheet = line.split(':', 1)[1].strip()[:100]
            page = None
    if page is not None:
        return {'kind':'page','value':page,'line':at_line}
    if sheet:
        return {'kind':'sheet','value':sheet,'line':at_line}
    return {'kind':'line','value':at_line}

def analyze_documents(tz_text: str, proposals: list[tuple[str,str]]) -> dict[str,Any]:
    from .laptop_analysis import compare_laptop
    specialized=compare_laptop(tz_text,proposals)
    if specialized is not None:
        return specialized
    # Preserve EVERY numbered procurement requirement, not one per known numeric field.
    from .numbered_analysis import analyze_numbered
    numbered=analyze_numbered(tz_text,proposals)
    if numbered is not None:
        return numbered
    requirements=_items(tz_text, True)
    if not requirements:
        # Preserve *all uploaded suppliers* even when no machine-checkable
        # requirements can be extracted. Never silently show a blank result.
        return {'requirements':[],
                'suppliers':[{'name':name[:100],'checks':[],'passed':0,'failed':0,
                              'unknown':0,'mandatory_failed':0,'mandatory_unknown':1,
                              'coverage_percent':0,'facts':_items(text,False)}
                             for name,text in proposals],
                'recommended':None,
                'warning':'Не удалось выделить проверяемые требования из ТЗ. Все КП требуют ручной проверки. Уточните формулировки ТЗ, например «Мощность не менее 5 кВт».',
                'engine':'rules-v1'}
    suppliers=[]
    for name,text in proposals:
        facts=_items(text,False)
        found={p['key']:p for p in facts}
        checks=[]
        for req in requirements:
            fact=found.get(req['key'])
            if not fact:
                status='unknown'; reason='Параметр не найден — необходима проверка специалиста'
            else:
                a,b=fact['value'],req['value']
                tolerance=max(1e-9,abs(b)*1e-7)
                valid= a>=b-tolerance if req['operator']=='min' else a<=b+tolerance if req['operator']=='max' else abs(a-b)<=tolerance
                status='pass' if valid else 'fail'
                reason='Требование выполнено' if valid else 'Значение не соответствует требованию'
            checks.append({'parameter':req['parameter'], 'required': req['value'], 'actual': fact['value'] if fact else None,
                           'unit':req['unit'],'operator':req['operator'], 'status':status, 'reason':reason,
                           'requirement_source':req['source'],'offer_source':fact['source'] if fact else None,
                           'requirement_locator':_source_locator(tz_text,req['line']),
                           'offer_locator':_source_locator(text,fact['line']) if fact else None})
        passed=sum(c['status']=='pass' for c in checks)
        failed=sum(c['status']=='fail' for c in checks)
        unknown=sum(c['status']=='unknown' for c in checks)
        # Percent is coverage/pass of extracted numeric constraints, NOT model confidence.
        percent=round(passed/len(checks)*100)
        suppliers.append({'name':name[:100],'checks':checks,'passed':passed,'failed':failed,'unknown':unknown,
                          'coverage_percent':percent,'facts':facts})
    eligible=[s for s in suppliers if s['failed']==0 and s['unknown']==0]
    eligible.sort(key=lambda s:(-s['passed'], next((f['value'] for f in s['facts'] if f['key']=='price'),float('inf'))))
    recommended=eligible[0]['name'] if eligible else None
    warning= ('Рекомендация предварительная: итоговое решение требует проверки человеком.' if recommended else
              'Нет полностью подтверждённого соответствия всем распознанным требованиям. Требуется проверка специалиста.')
    return {'requirements':requirements,'suppliers':suppliers, 'recommended':recommended,'warning':warning, 'engine':'rules-v1'}
