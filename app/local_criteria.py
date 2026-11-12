"""Local, source-grounded requirement extraction and interval comparison.

Rules are an explicit baseline, not an assertion of universal language understanding.
Unknown units, conflicting declarations, unsupported logic and missing evidence remain UNKNOWN.
"""
from __future__ import annotations
import re
import math
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
 'os':r'совместимост\w*(?: с ос)?|операционн\w* систем\w*|поддерж\w*(?=\s+android)',
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
 (r'квт|kw|киловатт\w*','power',1000,'Вт'),
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
 (r'тб|tb','storage',1000,'ГБ'),(r'гб|gb','storage',1,'ГБ'),
 (r'мб|mb','storage',0.001,'ГБ'),(r'ггц|ghz','frequency',1e9,'Гц'),
 (r'мгц|mhz','frequency',1e6,'Гц'),(r'кгц|khz','frequency',1000,'Гц'),
 (r'гц|hz','frequency',1,'Гц'),(r'нит\w*|кд/м[²2]','brightness',1,'нит'),
 (r'ма[·\s-]?ч|mah','capacity',1,'мА·ч'),(r'а[·\s-]?ч|ah','capacity',1000,'мА·ч'),
 (r'°\s*c|°\s*с|градус\w* цельсия','temperature',1,'°C'),
 (r'тыс\.?\s*руб\w*','price',1000,'₽'),(r'млн\.?\s*руб\w*','price',1e6,'₽'),
 (r'руб\w*\.?|₽|rub','price',1,'₽'),(r'%','percent',1,'%'),
]
NUMBER=r'[+-]?(?:\d{1,3}(?:[ \u00a0]\d{3})+|\d+)(?:[.,]\d+)?'
U_RE='(?:'+'|'.join(p for p,_,_,_ in UNITS)+')'
NUMUNIT=re.compile(r'(?<![\w.,])(?P<num>'+NUMBER+r')\s*(?:(?:календарн\w*|рабоч\w*)\s+)?(?P<unit>'+U_RE+r')(?!\w)',re.I)
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
    def cmp(a,b):
        return 0 if math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-9) else (1 if a>b else -1)
    def lower_inside():
        return req.lo is None or (offer.lo is not None and
               (cmp(offer.lo,req.lo)>0 or cmp(offer.lo,req.lo)==0 and (req.lo_closed or not offer.lo_closed)))
    def upper_inside():
        return req.hi is None or (offer.hi is not None and
               (cmp(offer.hi,req.hi)<0 or cmp(offer.hi,req.hi)==0 and (req.hi_closed or not offer.hi_closed)))
    if lower_inside() and upper_inside():return 'pass'
    if req.lo is not None and offer.hi is not None:
        if cmp(offer.hi,req.lo)<0 or cmp(offer.hi,req.lo)==0 and not(req.lo_closed and offer.hi_closed):return 'fail'
    if req.hi is not None and offer.lo is not None:
        if cmp(offer.lo,req.hi)>0 or cmp(offer.lo,req.hi)==0 and not(req.hi_closed and offer.lo_closed):return 'fail'
    return 'unknown'

def numeric(body,key,requirement=False,expected_dim=None):
    t=words_to_numbers(body)
    # Do not silently reduce alternatives, tolerances or contextual measurements.
    if re.search(r'\bили\b|приблизительно|около\b|~',t):return None
    dim=expected_dim or DIM.get(key)
    # Explicit tolerance, either absolute or percent, is an allowed interval.
    tol=re.search(r'('+NUMBER+r')\s*('+U_RE+r')?\s*(?:с допуском\s*)?±\s*('+NUMBER+r')\s*('+U_RE+r')(?!\w)',t,re.I)
    if tol:
        a=unit_info(tol.group(2) or tol.group(4));b=unit_info(tol.group(4))
        if not a or not b or dim and a[0]!=dim or b[0] not in (a[0],'percent'):return None
        if b[0]=='percent' and not tol.group(2):return None
        center=num(tol.group(1))*a[1];delta=num(tol.group(3))
        delta=abs(center)*delta/100 if b[0]=='percent' else delta*b[1]
        if delta<0 or not math.isfinite(center) or not math.isfinite(delta):return None
        if NUMUNIT.search(t[:tol.start()]+t[tol.end():]):return None
        return Interval(center-delta,center+delta,a[0],a[2])
    if '±' in t or 'допуск' in t:return None
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
    if re.search(r'(?:не более|не выше|не больше|не дольше|не превышает|не долж(?:ен|на|но|ны) превышать|максимум|до|<=|≤)\s*$',prefix):
        return Interval(None,val,dim,unit)
    if re.search(r'(?:более|выше|больше|свыше|>)\s*$',prefix):return Interval(val,None,dim,unit,False,True)
    if re.search(r'(?:менее|ниже|меньше|<)\s*$',prefix):return Interval(None,val,dim,unit,True,False)
    # "партия 100 шт." is treated as capacity, unless exact quantity is stated.
    if requirement and key=='quantity' and 'партия' in prefix and not re.search(r'\bровно\b|\bточно\b|=\s*$',prefix):
        return Interval(val,None,dim,unit)
    if re.search(r'\bне\s*$',prefix):return None
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
                body_keys={m.lastgroup for m in ALIAS_RE.finditer(norm(body))}
                label_key=classify(label)
                # A generic heading can contain several independent requirements.
                if label_key=='other' and len(body_keys)>=2:
                    out.extend(row_parts(body))
                else:
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
                if qty:out.append(dict(key='quantity',parameter=LABELS['quantity'],body='партия '+qty.group(),source=src,line=n))
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
        reason={'pass':'Числовое условие подтверждено','fail':'Интервалы требования и КП не пересекаются',
                'unknown':'Возможное соответствие: границы КП не гарантируют выполнение требования'}[status]
        factor=24 if k in ('battery','delivery') and ri.dim=='time' else 25.4 if k=='display' and ri.dim=='length' else 1
        unit=('суток' if k=='battery' else 'дней') if factor==24 else 'дюйма' if factor==25.4 else ri.unit
        required=required/factor
        actual=(oi.lo if oi.lo is not None else oi.hi)/factor
        if oi.lo is not None and oi.hi is not None and oi.lo!=oi.hi:
            actual=f'{oi.lo/factor:g}–{oi.hi/factor:g}'
        return status,reason,required,actual,unit,op
    # Numeric-looking but ambiguous: no fallback to a first number or text equality.
    if k in DIM or NUMUNIT.search(norm(r)):
        return 'unknown','Условие не удалось однозначно нормализовать',None,None,'','eq'
    targets={'os':'android','connection':'bluetooth','notifications':r'мессенджер\w*',
             'sensors':r'пульсометр\w*|сердцедатчик\w*','form':r'наручн\w*',
             'water':r'ip\s*\d{2}'}
    target=targets.get(k)
    if target:
        neg=r'(?:не\s+(?:поддержива\w*|совместим\w*|предусмотр\w*|име\w*)\s*(?:с\s+)?|без\s+|нет\s+|отсутствует\s+)(?:'+target+r')'
        if re.search(neg,norm(o)) or re.fullmatch(r'(?:нет|отсутствует|не предусмотрено)[.]?',norm(o)):
            return 'fail','В КП явно указано отсутствие требуемой характеристики',r,o,'','eq'
    if k in ('os','connection'):
        protocol='android' if k=='os' else 'bluetooth'
        if protocol in norm(r):
            if protocol not in norm(o):
                return 'unknown','Поддержка требуемой технологии не подтверждена',r,o,'','eq'
            version=re.search(protocol+r'\s*(\d+(?:[.,]\d+)*)(\+)?',norm(r))
            if version:
                ov=re.search(protocol+r'\s*(\d+(?:[.,]\d+)*)(\+)?',norm(o))
                if not ov:return 'unknown','Версия технологии не подтверждена',r,o,'','eq'
                def ver(m):return tuple(int(x) for x in re.split(r'[.,]',m.group(1)))
                a,b=ver(ov),ver(version)
                # Android N+ means minimum supported OS version: a higher
                # minimum does not guarantee compatibility with older devices.
                if k=='os':
                    if version.group(2) and ov.group(2):valid=a<=b
                    else:return 'unknown','Нужно проверить совместимость с требуемой версией ОС',r,o,'','eq'
                else:
                    if version.group(2):valid=a>=b
                    else:valid=a==b
                return ('pass' if valid else 'fail'),'Сравнение версий технологии',r,o,'','eq'
    if k in ('water','form','os','notifications','sensors','connection'):
        st,reason,needed,actual,unit=old_evaluate(dict(key=k,body=r),offer['parameter']+': '+o)
        return st,reason,needed,actual,unit,'eq'
    if norm(r).strip('.')==norm(o).strip('.') and not re.search(r'\bили\b|(?:не |без )',norm(r)):
        return 'pass','Точное совпадение формулировки',r,o,'','eq'
    return 'unknown','Нужна ручная проверка смыслового условия',r,o,'','eq'

def editable_records(tz_text,overrides=None):
    """Manual corrections are interpretations, never rewritten source quotes."""
    reqs=records(tz_text,True)
    for i,r in enumerate(reqs,1):
        r['section']=f'local-{i}'
        r['mandatory']=not bool(re.search(r'\b(?:желательно|необязательно|опционально)\b',norm(r['source'])))
        r['original_parameter']=r['parameter']
        r['original_body']=r['body']
        change=(overrides or {}).get(r['section'])
        if change:
            r.update(parameter=change['parameter'],body=change['condition'],mandatory=change['mandatory'])
            r['key']=classify(r['parameter'])
            r['edited']=True
    return reqs

def analyze_local(tz_text,proposals,retrieval=None,overrides=None):
    # Semantic candidates get priority for the displayed evidence, but every
    # same-parameter source row is still checked for contradictions.
    preferred={}
    for item in (retrieval or {}).get('results',[]):
        preferred[(item.get('supplier'),item.get('section'))]={
            f.get('line'):i for i,f in enumerate(item.get('fragments',[]))}
    reqs=editable_records(tz_text,overrides)
    if not reqs:return None
    requirements=[]
    for r in reqs:
        requirements.append(dict(id=r['section'],section=r['section'],key=r['key'],parameter=r['parameter'],
                                 source=r['source'],criterion_text=r['body'],line=r['line'],mandatory=r['mandatory'],
                                 edited=r.get('edited',False),original_parameter=r['original_parameter'],
                                 original_condition=r['original_body']))
    suppliers=[]
    for name,text in proposals:
        offered=records(text,False);checks=[]
        for r in reqs:
            candidates=[o for o in offered if same(r,o)]
            order=preferred.get((name,r['section']),{})
            candidates.sort(key=lambda o:(order.get(o['line'],10**9),o['line']))
            results=[(evaluate_pair(r,o),o) for o in candidates]
            valid=[(x,o) for x,o in results if x[0] in ('pass','fail')]
            if not results:
                st,reason,needed,actual,unit,op=evaluate_pair(r,dict(body='',parameter=r['parameter']))
                st='unknown';reason='В КП не найдено подтверждение того же параметра';actual=None
                evidence=None
            else:
                (st,reason,needed,actual,unit,op),evidence=(valid or results)[0]
                # Conflicting or uncertain duplicate declarations cannot certify a match.
                if len(results)>1 and (len({(x[0],str(x[3])) for x,o in results})>1):
                    st='unknown';reason='В КП несколько неоднозначных или противоречивых значений'
            ri=numeric(r['body'],r['key'],True)
            factor=24 if r['key'] in ('battery','delivery') and ri and ri.dim=='time' else 25.4 if r['key']=='display' and ri and ri.dim=='length' else 1
            upper=ri.hi/factor if ri and op=='range' and ri.hi is not None else None
            checks.append(dict(section=r['section'],id=r['section'],parameter=r['parameter'],operator=op,upper=upper,
                required=needed,actual=actual,unit=unit,status=st,reason=reason,mandatory=r['mandatory'],
                criterion_text=r['body'],edited=r.get('edited',False),requirement_source=r['source'],offer_source=evidence['source'] if evidence else None,
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


def annotate_evidence(tz_text,proposals,retrieval,overrides=None):
    """Independently validate each retrieved source ROW.

    Scores are never translated into a compliance probability. A candidate
    without a known parameter identity remains unconfirmed, regardless of
    cosine similarity. No report statuses or ranking are modified here.
    """
    reqs={r['section']:r for r in editable_records(tz_text,overrides)}
    offered={}
    for name,text in proposals:
        by_line={}
        for row in records(text,False):
            by_line.setdefault(row['line'],[]).append(row)
        offered[name]=by_line
    for item in retrieval.get('results',[]):
        r=reqs.get(item.get('section'))
        if r is None:continue
        for f in item.get('fragments',[]):
            candidates=[o for o in offered.get(item.get('supplier'),{}).get(f.get('line'),[])
                        if same(r,o)]
            if not candidates:
                f['parameter_match']='unconfirmed'
                f['verification_status']='unknown'
                f['verification_reason']='Релевантная строка, но тождество параметра не подтверждено'
                continue
            results=[evaluate_pair(r,o) for o in candidates]
            status=results[0][0]
            reason=results[0][1]
            if len({(x[0],str(x[3])) for x in results})>1:
                status='unknown';reason='В исходной строке несколько противоречивых значений'
            f['parameter_match']='confirmed'
            f['verification_status']=status
            f['verification_reason']=reason
            f['verified_source']=candidates[0]['source']
    return retrieval
