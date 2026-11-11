"""Key:value technical specification parser. Keep ALL criteria, cite evidence, be conservative."""
from __future__ import annotations
import re
from .analysis import _items, _source_locator

PATTERNS={
'form':[r'^форм[ -]?фактор'],'display':[r'^дисплей',r'^экран'],
'os':[r'^совместимост',r'^поддержк.*ос'],
'notifications':[r'^уведомлен'],'sensors':[r'^датчик'],
'battery':[r'^автономност',r'^время работы'],
'water':[r'^водозащит',r'^влагозащит'],
'sports':[r'^спорт',r'^режимы спорт'],
'connection':[r'^связь',r'^bluetooth',r'^беспроводн'],
'warranty':[r'^гаранти'],
'shipping':[r'^условия поставк',r'^поставк',r'^срок поставк'],
'quantity':[r'^количеств',r'^объем поставк'],
'delivery':[r'^срок доставк']}
NUM=r'(\d+(?:[.,]\d+)?)'
COUNT=r'(\d+)\s*(?:шт\.?|штук\b|единиц\b)'
DAYS=r'(\d+)\s*(?:календарн\w*\s*)?(?:д(?:ней|ня|ень)|сут(?:ок|ки)?|дн\.)\b'

def norm(text):
    return re.sub(r'\s+',' ',text.casefold().replace('ё','е')).strip()

def kind(label):
    text=norm(label)
    return next((k for k,aliases in PATTERNS.items() if any(re.search(p,text) for p in aliases)),None)

def criteria(tz):
    out=[]
    for line_no,raw in enumerate(tz.splitlines(),1):
        line=raw.strip()
        if ':' not in line:continue
        label,body=[v.strip() for v in line.split(':',1)]
        if not label or not body or len(label)>90:continue
        category=kind(label)
        # Preserve even unfamiliar attributes, mark UNKNOWN if no safe check.
        if category=='shipping':
            added=False
            for k,title,pattern in [('quantity','Количество в партии',COUNT),('delivery','Срок поставки',DAYS)]:
                if re.search(pattern,body,re.I):
                    out.append({'key':k,'parameter':title,'body':body,'source':line,
                                'line':line_no,'section':f'line-{line_no}-{k}'})
                    added=True
            if added:continue
        out.append({'key':category or 'unknown','parameter':label,'body':body,
                    'source':line,'line':line_no,'section':f'line-{line_no}-{category or "other"}'})
    if len(set(r['line'] for r in out))<3:return []
    return out

def offer(text,k):
    for line_no,raw in enumerate(text.splitlines(),1):
        raw=raw.strip()
        if ':' not in raw:continue
        label=raw.split(':',1)[0]
        typ=kind(label)
        if typ==k or k in ('quantity','delivery') and typ=='shipping':
            return line_no,raw
    return None,None

def number(pat,text):
    match=re.search(pat,norm(text),re.I)
    return float(match.group(1).replace(',','.')) if match else None

def evaluate(requirement,quote):
    if not quote:return 'unknown','В КП нет подтверждения',None,None,''
    k=requirement['key'];r=norm(requirement['body']);o=norm(quote.split(':',1)[1])
    def done(valid,need,actual,unit='',note=''):
        return ('pass' if valid else 'fail',note or ('Требование подтверждено' if valid else 'Нарушено требование'),need,actual,unit)
    if k in ('display','battery','sports','quantity','delivery'):
        patterns={'display':NUM+r'\s*(?:дюйм\w*|[″"])',
                  'battery':NUM+r'\s*(?:сут\w*|день|дней|дня)',
                  'sports':NUM+r'\s*режим\w*',
                  'quantity':COUNT,'delivery':DAYS}
        need=number(patterns[k],r);actual=number(patterns[k],o)
        if k=='sports' and need is None:
            need=number(r'(?:не менее|от|минимум)\s*'+NUM,r)
        unit={'display':'дюйма','battery':'суток','sports':'режимов','quantity':'шт.','delivery':'дней'}[k]
        if need is None or actual is None:
            return 'unknown','Не удалось извлечь сравнимое значение',need,actual,unit
        if k=='quantity':return done(actual>=need,need,actual,unit,'Партия достаточна' if actual>=need else 'Партия меньше требуемой')
        if k=='delivery':return done(actual<=need,need,actual,unit)
        if k=='battery' and 'до ' in o:
            if actual<need:return done(False,need,actual,unit,'Даже указанный максимум ниже минимального требования')
            return 'unknown','«До» означает максимум, а не гарантированный минимум',need,actual,unit
        return done(actual>=need,need,actual,unit)
    if k=='water':
        required=re.search(r'\bip\s*(\d{2})\b',r)
        actual=re.search(r'\bip\s*(\d{2})\b',o)
        if not required:return 'unknown','Нельзя определить стандарт IP',None,None,''
        if not actual:
            return 'unknown','Нет класса IP; ATM нельзя автоматически приравнять к IP', 'IP'+required.group(1),None,''
        a='IP'+actual.group(1);n='IP'+required.group(1)
        return done(a==n,n,a,'','Класс IP совпадает' if a==n else 'Класс IP не соответствует')
    if k=='form' and 'наручн' in r:return done('наручн' in o,'наручные',o)
    if k=='os' and 'android' in r:return done('android' in o,'Android',o)
    if k=='notifications' and 'мессенджер' in r:
        if 'мессенджер' in o:return done(True,'мессенджеры',o)
        return 'unknown','Поддержка уведомлений мессенджеров не подтверждена','мессенджеры',o,''
    if k=='sensors' and 'пульсометр' in r:
        if 'пульсометр' in o or 'сердцедатчик' in o:return done(True,'пульсометр',o)
        return 'unknown','Пульсометр не подтверждён','пульсометр',o,''
    if k=='connection' and 'bluetooth' in r:return done('bluetooth' in o,'Bluetooth',o)
    if k=='warranty':
        pattern=NUM+r'\s*(месяц\w*|мес\.?|год\w*|лет)'
        m=re.search(pattern,r);p=re.search(pattern,o)
        if not m or not p:return 'unknown','Срок гарантии отсутствует или не распознан',None,None,'мес.'
        def months(match):
            value=float(match.group(1).replace(',','.'))
            return value*12 if match.group(2).startswith(('год','лет')) else value
        return done(months(p)>=months(m),months(m),months(p),'мес.')
    return 'unknown','Нужна проверка данного текстового требования',None,None,''

def analyze_colon(tz_text,proposals):
    original=criteria(tz_text)
    if not original:return None
    reqs=[{'id':r['section'],'section':r['section'],'parameter':r['parameter'],
           'source':r['source'],'mandatory':True} for r in original]
    suppliers=[]
    for name,text in proposals:
        checks=[]
        for r in original:
            line,quote=offer(text,r['key'])
            status,reason,need,actual,unit=evaluate(r,quote)
            checks.append({'section':r['section'],'parameter':r['parameter'],'required':need,
                           'actual':actual,'unit':unit,'mandatory':True,
                           'status':status,'reason':reason,'requirement_source':r['source'],
                           'offer_source':quote,
                           'requirement_locator':_source_locator(tz_text,r['line']),
                           'offer_locator':_source_locator(text,line) if line else None})
        passed=sum(c['status']=='pass' for c in checks)
        failed=sum(c['status']=='fail' for c in checks)
        unknown=sum(c['status']=='unknown' for c in checks)
        suppliers.append({'name':name[:255],'checks':checks,
                          'passed':passed,'failed':failed,'unknown':unknown,
                          'mandatory_failed':failed,'mandatory_unknown':unknown,
                          'mandatory_passed':passed,
                          'coverage_percent':round(100*passed/len(checks)),
                          'facts':_items(text,False)})
    return {'requirements':reqs,'suppliers':suppliers,'recommended':None,
            'warning':'Все условия из ТЗ учтены; непроверенные требования требуют подтверждения.',
            'engine':'colon-criteria-v1'}
