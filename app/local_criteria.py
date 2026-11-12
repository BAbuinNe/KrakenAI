"""Local, source-grounded requirement extraction and interval comparison.

Rules are an explicit baseline, not an assertion of universal language understanding.
Unknown units, conflicting declarations, unsupported logic and missing evidence remain UNKNOWN.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from .analysis import _items, _source_locator
from .criteria_analysis import evaluate as old_evaluate

def norm(s):
    return re.sub(r'\s+', ' ', s.casefold().replace('ё','е')).strip()

# Aliases are parameter identities, not unit identities: duration of delivery
# and battery life must never match just because both are measured in days.
ALIASES={
 'battery':r'автономност\w*|время работы(?: без подзарядки)?|срок работы без подзарядки|работ\w* без подзарядки',
 'delivery':r'срок(?:и)? (?:поставки|доставки)|срок исполнения',
 'warranty':r'гаранти\w*(?: срок)?|гарантийн\w* срок',
 'display':r'диагонал\w*(?: экрана| дисплея)?|дисплей|экран',
 'sports':r'спортивн\w* режим\w*|режим\w* спорт\w*|спорт',
 'quantity':r'количество(?: товара| изделий)?|партия|объем поставки',
 'power':r'(?:номинальн\w* |максимальн\w* |потребляем\w* )?мощност\w*(?: двигателя)?',
 'voltage':r'напряжени\w*',
 'pressure':r'давлени\w*',
 'mass':r'масс[аыуе]|вес',
 'price':r'цен[ауы]|стоимост\w*|бюджет',
 'ram':r'оперативн\w* памят\w*|озу|ram',
 'storage':r'объем (?:накопителя|ssd)|накопител\w*|ssd',
 'brightness':r'яркост\w*',
 'length':r'длин[аыуе]',
 'width':r'ширин[аыуе]',
 'height':r'высот[аыуе]',
 'temperature':r'температур\w*',
 'frequency':r'частот\w*',
 'capacity':r'емкост\w* аккумулятор\w*|емкост\w* батаре\w*',
 'water':r'водозащит\w*|влагозащит\w*|степен\w* защиты|класс защиты',
 'form':r'форм[ -]?фактор',
 'os':r'совместимост\w*(?: с ос)?|операционн\w* систем\w*|поддерж\w* android',
 'notifications':r'уведомлен\w*',
 'sensors':r'датчик\w*(?: здоровья)?|пульсометр|сердцедатчик',
 'connection':r'связь(?: и навигация)?|bluetooth|беспроводн\w* связ\w*',
 'model':r'модель|маркировк\w*',
 'color':r'цвет',
 'material':r'материал(?: корпуса)?',
 'packaging':r'упаковк\w*',
 'condition':r'состояни\w*',
}
ALIAS_RE=re.compile(r'(?<!\w)(?:'+'|'.join('(?P<'+k+'>'+v+')' for k,v in ALIASES.items())+r')(?!\w)',re.I)
LABELS={'battery':'Автономность','delivery':'Срок поставки','quantity':'Количество в партии'}
DIM={'battery':'time','delivery':'time','warranty':'months','display':'length','sports':'count',
     'quantity':'count','power':'power','voltage':'voltage','pressure':'pressure','mass':'mass',
     'price':'price','ram':'storage','storage':'storage','brightness':'brightness',
     'length':'length','width':'length','height':'length','temperature':'temperature',
     'frequency':'frequency','capacity':'capacity'}
# Each unit has its dimension, canonical scale and canonical display unit.
UNITS=[
 (r'квт|kw|киловатт\w*','power',1000,'Вт'),(r'мвт|mw','power',1e6,'Вт'),
 (r'вт|w|ватт\w*','power',1,'Вт'),
 (r'кв|kv|киловольт\w*','voltage',1000,'В'),(r'в|v|вольт\w*','voltage',1,'В'),
 (r'мпа|mpa','pressure',1e6,'Па'),(r'кпа|kpa','pressure',1000,'Па'),
 (r'бар|bar','pressure',1e5,'Па'),(r'па|pa','pressure',1,'Па'),
 (r'кг|kg|килограмм\w*','mass',1000,'г'),(r'г|g|грамм\w*','mass',1,'г'),
 (r'мм|mm|миллиметр\w*','length',1,'мм'),(r'см|cm|сантиметр\w*','length',10,'мм'),
 (r'м|m|метр\w*','length',1000,'мм'),(r'дюйм\w*|inch(?:es)?|[″"]','length',25.4,'мм'),
 (r'сут\w*|день|дня|дней|дн\.?|day(?:s)?','time',24,'ч'),
 (r'недел\w*|week(?:s)?','time',168,'ч'),(r'час\w*|ч\.?|hours?|h','time',1,'ч'),
 (r'минут\w*|мин\.?','time',1/60,'ч'),
 (r'месяц\w*|мес\.?|months?','months',1,'мес.'),
 (r'год\w*|лет|years?','months',12,'мес.'),
 (r'шт\.?|штук\w*|единиц\w*|режим\w*','count',1,'шт.'),
 (r'тб|tb','storage',1024,'ГБ'),(r'гб|gb','storage',1,'ГБ'),
 (r'мб|mb','storage',1/1024,'ГБ'),(r'ггц|ghz','frequency',1e9,'Гц'),
 (r'мгц|mhz','frequency',1e6,'Гц'),(r'кгц|khz','frequency',1000,'Гц'),
 (r'гц|hz','frequency',1,'Гц'),(r'нит\w*|кд/м[²2]','brightness',1,'нит'),
 (r'ма[·\s-]?ч|mah','capacity',1,'мА·ч'),(r'а[·\s-]?ч|ah','capacity',1000,'мА·ч'),
 (r'°\s*c|°\s*с|градус\w* цельсия','temperature',1,'°C'),
 (r'тыс\.?\s*руб\w*','price',1000,'₽'),(r'млн\.?\s*руб\w*','price',1e6,'₽'),
 (r'руб\w*\.?|₽|rub','price',1,'₽'),(r'%','percent',1,'%'),
]
NUMBER=r'[+-]?(?:\d{1,3}(?:[ \u00a0]\d{3})+|\d+)(?:[.,]\d+)?'
U_RE='(?:'+'|'.join(p for p,_,_,_ in UNITS)+')'
NUMUNIT=re.compile(r'(?<![\w.,])(?P<num>'+NUMBER+r')\s*(?P<unit>'+U_RE+r')(?!\w)',re.I)
WORD_NUM={'один':1,'одна':1,'одного':1,'два':2,'двух':2,'три':3,'трех':3,'четыре':4,'четырех':4,
          'пять':5,'пяти':5,'шесть':6,'шести':6,'семь':7,'семи':7,'восемь':8,'восьми':8,
          'девять':9,'девяти':9,'десять':10,'десяти':10}
def words_to_numbers(s):
    return re.sub(r'\b(?:'+'|'.join(WORD_NUM)+r')\b',lambda m:str(WORD_NUM[m.group(0)]),norm(s))

def unit_info(unit):
    for pat,dim,scale,canonical in UNITS:
        if re.fullmatch(pat,unit,re.I):return dim,scale,canonical
    return None

def num(s):return float(s.replace(' ','').replace('\u00a0','').replace(',','.'))

@dataclass(frozen=True)
class Interval:
    lo:float|None
    hi:float|None
    dim:str
    unit:str
    lo_closed:bool=True
    hi_closed:bool=True

def relation(req,offer):
    """Subset => PASS; disjoint => FAIL; otherwise UNKNOWN. Open bounds included."""
    if req.dim!=offer.dim:return 'unknown'
    def lower_inside():
        return req.lo is None or (offer.lo is not None and
               (offer.lo>req.lo or offer.lo==req.lo and (req.lo_closed or not offer.lo_closed)))
    def upper_inside():
        return req.hi is None or (offer.hi is not None and
               (offer.hi<req.hi or offer.hi==req.hi and (req.hi_closed or not offer.hi_closed)))
    if lower_inside() and upper_inside():return 'pass'
    if req.lo is not None and offer.hi is not None:
        if offer.hi<req.lo or offer.hi==req.lo and not(req.lo_closed and offer.hi_closed):return 'fail'
    if req.hi is not None and offer.lo is not None:
        if offer.lo>req.hi or offer.lo==req.hi and not(req.hi_closed and offer.lo_closed):return 'fail'
    return 'unknown'

def numeric(body,key,requirement=False,expected_dim=None):
    t=words_to_numbers(body)
    # Do not silently reduce alternatives, tolerances or contextual measurements.
    if re.search(r'\bили\b|±|допуск|приблизительно|около\b|~',t):return None
    dim=expected_dim or DIM.get(key)
    # Range with one shared unit or identical dimensional units.
    rg=re.search(r'(?:\bот\s*)?('+NUMBER+r')\s*('+U_RE+r')?\s*(?:до|[–—-])\s*('+NUMBER+r')\s*('+U_RE+r')(?!\w)',t,re.I)
    if rg:
        a,b=unit_info(rg.group(2) or rg.group(4)),unit_info(rg.group(4))
        if not a or not b or a[0]!=b[0] or dim and a[0]!=dim:return None
        lo,hi=num(rg.group(1))*a[1],num(rg.group(3))*b[1]
        if lo>hi:return None
        # Additional quantities are ambiguous, never choose one silently.
        tail=t[:rg.start()]+t[rg.end():]
        if NUMUNIT.search(tail):return None
        return Interval(lo,hi,a[0],a[2])
    matches=[]
    for m in NUMUNIT.finditer(t):
        info=unit_info(m.group('unit'))
        if info and (not dim or info[0]==dim):matches.append((m,info))
    if len(matches)!=1:
        # Sports / count labels can supply the unit implicitly.
        if not matches and key in ('sports','quantity'):
            m=re.fullmatch(r'\s*(?:(?:не менее|не более|минимум|максимум|от|до|ровно|>=|<=|≥|≤)\s*)?('+NUMBER+r')\s*[.]?',t)
            if m:
                val=num(m.group(1));prefix=t[:m.start(1)]
                return bound(val,'count','шт.',prefix,key,requirement)
        return None
    m,info=matches[0]
    # Two values with different units (e.g. 5 kW at 220 V) are not one scalar.
    if len(list(NUMUNIT.finditer(t)))!=1:return None
    val=num(m.group('num'))*info[1]
    prefix=t[:m.start()].strip()
    return bound(val,info[0],info[2],prefix,key,requirement)

def bound(val,dim,unit,prefix,key,requirement):
    if re.search(r'(?:не менее|не ниже|не меньше|минимум|от|>=|≥)\s*$',prefix):
        return Interval(val,None,dim,unit)
    if re.search(r'(?:не более|не выше|не больше|не дольше|максимум|до|<=|≤)\s*$',prefix):
        return Interval(None,val,dim,unit)
    if re.search(r'(?:более|выше|больше|>)\s*$',prefix):return Interval(val,None,dim,unit,False,True)
    if re.search(r'(?:менее|ниже|меньше|<)\s*$',prefix):return Interval(None,val,dim,unit,True,False)
    # "партия 100 шт." is treated as capacity, unless exact quantity is stated.
    if requirement and key=='quantity' and not re.search(r'\bровно\b|\bточно\b|=\s*$',prefix):
        return Interval(val,None,dim,unit)
    return Interval(val,val,dim,unit)

def strip_number(s):
    return re.sub(r'^\s*(?:(?:\d+(?:\.\d+)*[.)]?)\s+|[-•]\s*)','',s).strip()

def classify(label):
    m=ALIAS_RE.search(norm(label))
    return m.lastgroup if m else 'other'

def row_parts(raw):
    s=strip_number(raw)
    if '|' in s:
        cells=[x.strip() for x in s.split('|') if x.strip()]
        if cells and re.fullmatch(r'\d+(?:\.\d+)*\.?',cells[0]):cells=cells[1:]
        if len(cells)>=2:
            if norm(cells[0]) in ('параметр','характеристика','наименование','критерий','показатель','требование'):return []
            return [(cells[0], ' '.join(cells[1:]))]
    # Split clauses without breaking decimal points.
    out=[]
    for part in re.split(r';\s*|(?<=[.!?])\s+(?=[А-ЯЁA-Z])',s):
        part=part.strip()
        if not part:continue
        if ':' in part:
            label,body=part.split(':',1)
            if len(label)<=90 and body.strip():
                out.append((label.strip(),body.strip()))
                continue
        matches=list(ALIAS_RE.finditer(norm(part)))
        # Multiple different known attributes in prose: preserve atomic clauses.
        if matches:
            anchors=[]
            for m in matches:
                if not anchors or m.lastgroup!=anchors[-1].lastgroup:
                    anchors.append(m)
            normalized=norm(part)
            for i,m in enumerate(anchors):
                stop=anchors[i+1].start() if i+1<len(anchors) else len(normalized)
                body=normalized[m.end():stop].strip(' ,.:;')
                if body:
                    out.append((m.group(0),body))
            if out:continue
        out.append((part,''))
    return out

def records(text,requirement):
    out=[]
    for n,raw in enumerate(text.splitlines(),1):
        src=raw.strip()
        if not src or re.fullmatch(r'(?:страница \d+:|лист:.*|техническое задание|коммерческое предложение|технические характеристики|требования к товару|условия поставки|характеристики товара)',norm(src)):continue
        for label,body in row_parts(src):
            k=classify(label)
            # Split compound shipment clauses using the original evidence.
            if re.search(r'поставк|доставк',norm(label)) and re.search(r'\d+\s*(?:шт\.?|штук\b)',norm(body)):
                qty=re.search(r'(?:(?:не менее|не более|ровно|от|до)\s+)?'+NUMBER+r'\s*(?:шт\.?|штук\b)',norm(body))
                days=re.search(r'(?:(?:не менее|не более|от|до)\s+)?'+NUMBER+r'\s*(?:календарн\w*\s*|рабоч\w*\s*)?(?:дней|дня|день|суток|недел\w*)',norm(body))
                if qty:out.append(dict(key='quantity',parameter=LABELS['quantity'],body=qty.group(),source=src,line=n))
                if days:out.append(dict(key='delivery',parameter=LABELS['delivery'],body=days.group(),source=src,line=n))
                continue
            if not body and not requirement:continue
            # Preserve an unrecognized requirement instead of silently dropping it.
            if not body:body=label
            out.append(dict(key=k,parameter=label,body=body,source=src,line=n))
    return out

def qualified(label):
    s=norm(label)
    return next((k for k in ('номинальн','максимальн','потребляем','минимальн','рабоч','пиков') if k in s),'')

def same(req,offer):
    if req['key']=='other':
        return offer['key']=='other' and norm(req['parameter'])==norm(offer['parameter'])
    if req['key']!=offer['key']:return False
    a,b=qualified(req['parameter']),qualified(offer['parameter'])
    return a==b or not(a or b)

def evaluate_pair(req,offer):
    k=req['key'];r=req['body'];o=offer['body']
    ri=numeric(r,k,True);oi=numeric(o,k,False,ri.dim if ri else None)
    if ri is not None:
        required=ri.lo if ri.lo is not None else ri.hi
        op='range' if ri.lo is not None and ri.hi is not None and ri.lo!=ri.hi else 'eq' if ri.lo==ri.hi else ('min' if ri.lo_closed else 'gt') if ri.lo is not None else ('max' if ri.hi_closed else 'lt')
        if oi is None or ri.dim!=oi.dim:
            return 'unknown','Нет однозначного числового значения в совместимых единицах',required,None,ri.unit,op
        if k=='delivery' and bool(re.search(r'рабоч',norm(r)))!=bool(re.search(r'рабоч',norm(o))):
            return 'unknown','Рабочие и календарные дни нельзя сравнивать без календаря',required,None,ri.unit,op
        status=relation(ri,oi)
        actual=oi.lo if oi.lo is not None else oi.hi
        if oi.lo is not None and oi.hi is not None and oi.lo!=oi.hi:
            actual=f'{oi.lo:g}–{oi.hi:g}'
        reason={'pass':'Числовое условие подтверждено','fail':'Интервалы требования и КП не пересекаются',
                'unknown':'Возможное соответствие: границы КП не гарантируют выполнение требования'}[status]
        # Preserve familiar display units for battery, delivery and screen.
        if k in ('battery','delivery') and ri.dim=='time':
            required=required/24
            actual=actual/24 if isinstance(actual,(float,int)) else actual
            unit='суток' if k=='battery' else 'дней'
        elif k=='display' and ri.dim=='length':
            required=required/25.4
            actual=actual/25.4 if isinstance(actual,(float,int)) else actual
            unit='дюйма'
        else:unit=ri.unit
        return status,reason,required,actual,unit,op
    # Numeric-looking but ambiguous: no fallback to a first number or text equality.
    if k in DIM or NUMUNIT.search(norm(r)):
        return 'unknown','Условие не удалось однозначно нормализовать',None,None,'','eq'
    if re.search(r'\b(?:не поддерживает|не предусмотрен\w*|отсутствует|нет|без)\b',norm(o)):
        if k in ('os','notifications','sensors','connection','form'):
            return 'fail','В КП явно указано отсутствие функции',r,o,'','eq'
    if k in ('water','form','os','notifications','sensors','connection'):
        st,reason,needed,actual,unit=old_evaluate(dict(key=k,body=r),offer['parameter']+': '+o)
        return st,reason,needed,actual,unit,'eq'
    if norm(r).strip('.')==norm(o).strip('.') and not re.search(r'\bили\b|(?:не |без )',norm(r)):
        return 'pass','Точное совпадение формулировки',r,o,'','eq'
    return 'unknown','Нужна ручная проверка смыслового условия',r,o,'','eq'

def analyze_local(tz_text,proposals):
    reqs=records(tz_text,True)
    if not reqs:return None
    requirements=[]
    for i,r in enumerate(reqs,1):
        r['section']=f'local-{i}'
        r['mandatory']=not bool(re.search(r'\b(?:желательно|необязательно|опционально)\b',norm(r['source'])))
        requirements.append(dict(id=r['section'],section=r['section'],key=r['key'],parameter=r['parameter'],
                                 source=r['source'],line=r['line'],mandatory=r['mandatory']))
    suppliers=[]
    for name,text in proposals:
        offered=records(text,False);checks=[]
        for r in reqs:
            candidates=[o for o in offered if same(r,o)]
            results=[(evaluate_pair(r,o),o) for o in candidates]
            valid=[(x,o) for x,o in results if x[0] in ('pass','fail')]
            if not results:
                ri=numeric(r['body'],r['key'],True)
                st,reason,needed,actual,unit,op='unknown','В КП не найдено подтверждение того же параметра',None,None,'','eq'
                evidence=None
            else:
                (st,reason,needed,actual,unit,op),evidence=(valid or results)[0]
                # Conflicting or uncertain duplicate declarations cannot certify a match.
                if len(results)>1 and (len({(x[0],str(x[3])) for x,o in results})>1):
                    st='unknown';reason='В КП несколько неоднозначных или противоречивых значений'
            checks.append(dict(section=r['section'],id=r['section'],parameter=r['parameter'],operator=op,
                required=needed,actual=actual,unit=unit,status=st,reason=reason,mandatory=r['mandatory'],
                requirement_source=r['source'],offer_source=evidence['source'] if evidence else None,
                requirement_locator=_source_locator(tz_text,r['line']),
                offer_locator=_source_locator(text,evidence['line']) if evidence else None))
        passed=sum(c['status']=='pass' for c in checks);failed=sum(c['status']=='fail' for c in checks)
        unknown=sum(c['status']=='unknown' for c in checks)
        mandatory=[c for c in checks if c['mandatory']]
        mp=sum(c['status']=='pass' for c in mandatory);mf=sum(c['status']=='fail' for c in mandatory)
        mu=sum(c['status']=='unknown' for c in mandatory)
        suppliers.append(dict(name=name[:255],checks=checks,passed=passed,failed=failed,unknown=unknown,
            mandatory_passed=mp,mandatory_failed=mf,mandatory_unknown=mu,
            coverage_percent=round(100*passed/len(checks)),facts=_items(text,False)))
    eligible=[s for s in suppliers if s['mandatory_failed']==s['mandatory_unknown']==0 and s['mandatory_passed']>0]
    eligible.sort(key=lambda s:(-s['passed'],next((f['value'] for f in s['facts'] if f['key']=='price'),float('inf'))))
    return dict(requirements=requirements,suppliers=suppliers,recommended=eligible[0]['name'] if eligible else None,
        warning='Проверены распознанные условия; неизвестные параметры и неоднозначности требуют подтверждения.',
        engine='colon-criteria-v1' if ':' in tz_text else 'local-criteria-v2')
