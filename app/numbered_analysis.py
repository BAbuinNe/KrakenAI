"""Conservative extraction of EVERY numbered TZ clause.
PASS requires explicit evidence; no clause disappears if rules cannot verify it.
"""
from __future__ import annotations
import re
from typing import Any

CLAUSE=re.compile(r'^\s*(?P<id>\d+\.\d+)\.\s*(?P<content>.+?)\s*$')
CATS={
 'type':('тип',),'model':('модель','маркировк'),'power':('мощност',),
 'volume':('рабочий объём','рабочий объем'),
 'cylinders':('число цилиндров','количество цилиндров'),
 'emission':('экологический класс','экокласс'),
 'cooling':('система охлаждения','охлажден'),
 'equipment':('комплектност','комплектация'),
 'condition':('состояние',),'resource':('ресурс',),
 'warranty':('гарантия','гарантийный срок'),
 'delivery':('срок поставки',),'terms':('условия поставки',),
 'documents':('документы','комплект документов'),
 'packaging':('упаковк',),'experience':('опыт поставок','опыт работы'),
 'support':('сервисной поддержки','сервисная поддержка','гарантийного ремонта'),
 'registry':('реестре недобросовестных','недобросовестных поставщик')
}
OFFER_TERMS={
 'type':('тип:',),'model':('модель:','маркировка:'),
 'power':('мощность:',),'volume':('рабочий объём:','рабочий объем:'),
 'cylinders':('число цилиндров:','количество цилиндров:'),
 'emission':('экологический класс:'),
 'equipment':('комплектность:','комплектация:'),
 'condition':('состояние:',),'resource':('ресурс:',),
 'warranty':('гарантия:','гарантийный срок:'),
 'delivery':('срок поставки:',),'packaging':('упаковка:')
}
PATTERNS={
 'power':r'(\d[\d\s]*(?:[.,]\d+)?)\s*(?:квт|киловатт)',
 'volume':r'(\d+(?:[.,]\d+)?)\s*л\b',
 'cylinders':r'(?<!\d)(\d{1,2})(?!\d)',
 'emission':r'евро\s*[-–]?\s*(\d+)',
 'resource':r'(\d[\d\s]*)\s*моточас',
 'warranty':r'(\d+)\s*(?:месяц|мес\.|мес\b|год|лет|года)',
 'delivery':r'(\d+)\s*(?:календарн\w*\s*)?(?:дн|день|дней|дня)',
 'experience':r'(\d+)\s*лет|(?<!\d)(\d+)\s*год'
}

def norm(text:str)->str:
    return text.casefold().replace('ё','е')

def category(label:str)->str|None:
    t=norm(label)
    return next((key for key,aliases in CATS.items()
                 if any(norm(alias) in t for alias in aliases)),None)

def clauses(tz:str)->list[dict[str,Any]]:
    out=[]
    for line_no,line in enumerate(tz.splitlines(),1):
        quantity=re.search(r'Количество\s*:\s*(\d+)\s*шт\.?',line,re.I)
        if quantity and not any(x['id']=='1.1' for x in out):
            out.append({'id':'1.1','parameter':'Количество',
                        'text':line.strip(),'description':'Количество: '+quantity.group(1)+' шт.',
                        'line':line_no,'category':'quantity'})
        m=CLAUSE.match(line)
        if not m:continue
        label,sep,description=m['content'].partition(':')
        if not sep:label,description=m['content'].rstrip('.'),m['content'].rstrip('.')
        out.append({'id':m['id'],'parameter':label.strip(),'text':line.strip(),
                    'description':description.strip(),'line':line_no,
                    'category':category(label)})
    return out

def candidate(text:str,cat:str|None)->tuple[int|None,str]:
    if cat is None:return None,''
    if cat=='quantity':
        for i,line in enumerate(text.splitlines(),1):
            if 'предмет предложения' in norm(line) and 'шт' in norm(line):
                return i,line.strip()
        return None,''
    for i,line in enumerate(text.splitlines(),1):
        s=line.strip()
        t=norm(s)
        if cat in OFFER_TERMS:
            if any(term in t[:115] for term in OFFER_TERMS[cat]):return i,s
        elif cat=='cooling' and 'охлажден' in t:return i,s
        elif cat=='terms' and ('доставка до склада' in t or 'разгрузк' in t):return i,s
        elif cat=='documents' and ('комплект документов' in t or 'паспорт-формуляр' in t):return i,s
        elif cat in ('experience','support','registry') and ('сведения о поставщике' in t or
                          (cat=='registry' and 'недобросовестн' in t)):return i,s
    return None,''

def amount(text:str,cat:str)->float|None:
    if cat=='cylinders' and ':' in text:text=text.split(':',1)[1]
    m=re.search(PATTERNS[cat],text,re.I) if cat in PATTERNS else None
    if not m:return None
    raw=next((g for g in m.groups() if g is not None),'')
    value=float(raw.replace(' ','').replace('\u00a0','').replace(',','.'))
    if cat=='warranty' and re.search(r'\b(?:год|года|лет)\b',m.group(0),re.I):
        value*=12
    return value

def has(text:str,*alternatives:str)->bool:
    t=norm(text)
    return any(norm(x) in t for x in alternatives)

def judge(req:dict,quote:str)->tuple[str,str,float|None,float|None,str]:
    cat=req['category']; r=norm(req['description']);p=norm(quote)
    if not quote:return 'unknown','В КП не обнаружено подтверждение пункта',None,None,''
    if cat=='quantity':
        expected=re.search(r'(\d+)\s*шт\.?',r)
        found=re.search(r'(\d+)\s*(?:\([^)]{0,18}\)\s*)?шт\.?',p)
        if not expected or not found:
            return 'unknown','Количество не подтверждено',None,None,'шт.'
        needed,actual=float(expected.group(1)),float(found.group(1))
        return ('pass' if actual==needed else 'fail','Количество соответствует' if actual==needed else 'Количество не соответствует',needed,actual,'шт.')
    if cat in ('power','resource','delivery','experience','cylinders','emission'):
        expected=amount(r,cat);found=amount(p,cat)
        if expected is None or found is None:
            return 'unknown','Числовое значение не извлечено',expected,found,''
        if cat in ('power','resource','experience','emission'):valid=found>=expected
        elif cat=='delivery':valid=found<=expected
        else:valid=found==expected
        units={'power':'кВт','resource':'моточасов','delivery':'дней',
               'experience':'лет','cylinders':'шт.','emission':'Евро'}
        return ('pass' if valid else 'fail','Значение соответствует требованию' if valid else
                'Нарушено числовое требование',expected,found,units[cat])
    if cat=='volume':
        expected=amount(r,'volume');found=amount(p,'volume')
        tolerance=re.search(r'±\s*(\d+(?:[.,]\d+)?)\s*%',r)
        if expected is None or found is None or not tolerance:
            return 'unknown','Не удалось определить объём или допуск',expected,found,'л'
        valid=abs(found-expected)<=expected*float(tolerance.group(1).replace(',','.'))/100+1e-8
        return 'pass' if valid else 'fail','Объём с учётом допуска' if valid else 'Объём вне допуска',expected,found,'л'
    if cat=='warranty':
        expected=amount(r,'warranty');found=amount(p,'warranty')
        if expected is None or found is None:
            return 'unknown','Гарантийный срок не найден',expected,found,'мес.'
        valid=found>=expected
        return 'pass' if valid else 'fail','Гарантийный срок подтверждён' if valid else 'Недостаточный срок гарантии',expected,found,'мес.'
    if cat=='type':
        if 'дизель' in r and '4-такт' in r and all([
            'дизель' in p,'4-такт' in p,has(p,'рядн','v-образн','v образн')]):
            return 'pass','Тип, тактность и конфигурация заявлены',None,None,''
    if cat=='model':
        return 'unknown','Соответствие модели штатному ДВС нужно проверить по документам ТС',None,None,''
    if cat=='cooling' and 'жидкостн' in r and 'жидкостн' in p:
        return 'pass','Жидкостное охлаждение указано',None,None,''
    if cat=='equipment':
        terms=('блок','гбц','тнвд','турбокомпрессор','генератор',
               'стартер','форсунк','жгут','навесн')
        missing=[x for x in terms if x in r and x not in p]
        if not missing and 'в сборе' in p:
            return 'pass','Все указанные компоненты перечислены в КП',None,None,''
        return 'unknown','Не подтверждена комплектность: '+', '.join(missing),None,None,''
    if cat=='condition' and 'нов' in r and 'нов' in p:
        return 'pass','Заявлено новое изделие',None,None,''
    if cat=='terms' and all(x in p for x in ('склад','разгрузк','поставщик')):
        return 'pass','Доставка до склада и разгрузка поставщиком заявлены',None,None,''
    if cat=='documents':
        groups=(('паспорт','формуляр'),('сертификат',),('гарантийн',),
                ('товарная накладная','упд'),('счет-фактура','счёт-фактура','упд'))
        if all(has(p,*g) for g in groups):
            if not has(p,'товарная накладная') and has(p,'упд'):
                return 'unknown','В КП указан УПД вместо отдельной накладной: проверить допустимость',None,None,''
            return 'pass','Документы заявлены',None,None,''
        return 'unknown','Не все документы подтверждены',None,None,''
    if cat=='packaging' and 'транспортн' in p and has(p,'тара','упаковк'):
        return 'pass','Транспортная тара заявлена',None,None,''
    if cat=='support' and (('сервисн' in p and 'центр' in p) or
                           ('гарантийн' in p and 'ремонт' in p)):
        return 'pass','Сервис или гарантийный ремонт заявлены',None,None,''
    if cat=='registry':
        return 'unknown','Нужно проверить поставщика в независимом реестре',None,None,''
    return 'unknown','Нет надёжного автоматического подтверждения',None,None,''

def analyze_numbered(tz_text:str,proposals:list[tuple[str,str]])->dict[str,Any]|None:
    reqs=clauses(tz_text)
    if len(reqs)<3:return None
    from .analysis import _items,_source_locator
    requirements=[{'id':r['id'],'section':r['id'],'parameter':r['parameter'],
                   'source':r['text'],'mandatory':True} for r in reqs]
    suppliers=[]
    for name,text in proposals:
        checks=[]
        for req in reqs:
            line,quote=candidate(text,req['category'])
            status,reason,needed,actual,unit=judge(req,quote)
            checks.append({'id':req['id'],'section':req['id'],
                           'parameter':req['parameter'],'required':needed,
                           'actual':actual,'unit':unit,'mandatory':True,
                           'status':status,'reason':reason,
                           'requirement_source':req['text'],
                           'offer_source':quote or None,
                           'requirement_locator':_source_locator(tz_text,req['line']),
                           'offer_locator':_source_locator(text,line) if line else None})
        passed=sum(c['status']=='pass' for c in checks)
        failed=sum(c['status']=='fail' for c in checks)
        unknown=sum(c['status']=='unknown' for c in checks)
        suppliers.append({'name':name[:255],'checks':checks,
                          'passed':passed,'failed':failed,'unknown':unknown,
                          'mandatory_failed':failed,'mandatory_unknown':unknown,
                          'coverage_percent':round(passed/len(checks)*100),
                          'facts':_items(text,False)})
    return {'requirements':requirements,'suppliers':suppliers,'recommended':None,
            'warning':'Учтены все нумерованные пункты ТЗ. Неподтверждённые условия требуют ручной проверки.',
            'engine':'numbered-criteria-v1'}
