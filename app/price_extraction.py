"""Conservative RUB price extraction with documentary evidence.

No guessing currency or totals from unrelated numbers. Multiple competing prices
are flagged ambiguous unless a clear final/total price is identified.
"""
from __future__ import annotations
import re

SPACE = r'[\s\u00a0\u202f]'
AMOUNT = r'\d{1,12}(?:'+SPACE+r'\d{3})*(?:[.,]\d{1,2})?'
CURRENCY = r'(?:₽|руб(?:лей|ля|\.)?|р\.|RUB)'
MULTIPLIER = r'(?:тыс(?:яч(?:и|а)?)?\.?|млн(?:\.|иллион(?:ов|а)?)?)'
LABEL = re.compile(r'(?<!\w)(?:итого|всего\s+к\s+оплате|общая\s+стоимость|'
                   r'итоговая\s+цена|цена|стоимость|сумма|бюджет|'
                   r'предложение\s+по\s+цене)(?!\w)', re.I)
TOTAL = re.compile(r'итого|всего\s+к\s+оплате|общая\s+стоимость|итоговая\s+цена',re.I)
# Explicit currency symbol and code can appear before or after number.
AFTER = re.compile(r'(?P<value>'+AMOUNT+r')'+SPACE+r'*(?P<mult>'+MULTIPLIER+r')?'+SPACE+
                   r'*(?P<currency>'+CURRENCY+r')(?!\w)',re.I)
BEFORE = re.compile(r'(?P<currency>₽|RUB)'+SPACE+r'*(?P<value>'+AMOUNT+r')',re.I)
# Currency can be omitted ONLY on a price-labeled line.
PLAIN = re.compile(r'(?P<value>'+AMOUNT+r')'+SPACE+r'*(?P<mult>'+MULTIPLIER+r')?(?!\s*(?:%|гб|кг|ггц|шт|шт\.|лет|мес))',re.I)
 
def _numeric(raw: str, multiplier: str = '') -> float:
    raw = re.sub(SPACE, '', raw)
    if ',' in raw and '.' in raw:
        # Russian decimal comma, dot may be a thousands separator.
        raw = raw.replace('.','').replace(',','.')
    elif ',' in raw:
        raw = raw.replace(',','.')
    elif '.' in raw and len(raw.rsplit('.',1)[1])==3:
        raw = raw.replace('.','')
    value = float(raw)
    if multiplier.lower().startswith('тыс'):value*=1000
    if multiplier.lower().startswith('млн'):value*=1_000_000
    return round(value,2)

def _context_score(line: str) -> int:
    if TOTAL.search(line): return 3
    if re.search(r'стоимость|цена|сумма',line,re.I): return 2
    return 1

def extract_rub_price(text: str) -> tuple[float | None, str | None, str]:
    """Return (rubles, source_line, reason). Unsupported currencies never converted."""
    hits: list[tuple[int,float,str]]=[]
    for original in text.splitlines():
        line = original.strip()
        if not line or len(line)>550:continue
        # Explicit non-RUB currency must not be treated as RUB just because of a label.
        foreign = bool(re.search(r'[$€]|\b(?:USD|EUR|CNY|KZT)\b',line,re.I))
        matches=list(AFTER.finditer(line)) + list(BEFORE.finditer(line))
        if matches:
            for match in matches:
                try:
                    val=_numeric(match.group('value'), match.groupdict().get('mult') or '')
                    if val>0:
                        hits.append((_context_score(line),val,line[:300]))
                except ValueError:pass
        elif LABEL.search(line) and not foreign:
            # Tables are flattened as "Price | 85 000 | RUB"; the first amount must
            # be unambiguous before assuming that an omitted currency is rubles.
            amounts=[m for m in PLAIN.finditer(line) if len(m.group('value'))>=3]
            if len(amounts)==1 and re.search(r'\bруб|₽|\bRUB\b',text,re.I):
                match=amounts[0]
                try:
                    val=_numeric(match.group('value'),match.group('mult') or '')
                    if val>0:hits.append((_context_score(line),val,line[:300]))
                except ValueError:pass
    if not hits:return None,None,'not_found'
    top=max(h[0] for h in hits)
    best=[h for h in hits if h[0]==top]
    distinct={h[1] for h in best}
    if len(distinct)!=1:return None,None,'ambiguous'
    return best[0][1],best[0][2],'found'
