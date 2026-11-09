"""Parser for PDF, DOCX, XLSX. Isolate in a separate unprivileged process."""
import base64
import io
import json
import os
import re
import sys
import zipfile

MAX_TEXT=15000

def safe_zip(data: bytes):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            files=z.infolist()
            if len(files)>350 or sum(f.file_size for f in files)>32*1024*1024:
                raise ValueError('Слишком большой архив')
            for f in files:
                if f.file_size>12*1024*1024 or (f.compress_size and f.file_size/f.compress_size>75):
                    raise ValueError('Подозрительное сжатие')
                if '..' in f.filename.split('/') or f.filename.startswith('/'):
                    raise ValueError('Недопустимый путь')
            return set(z.namelist())
    except zipfile.BadZipFile:
        raise ValueError('Некорректный Office-файл')

def extract(data:bytes,ext:str)->str:
    if ext=='.pdf':
        from pypdf import PdfReader
        if not data.startswith(b'%PDF-'): raise ValueError('Некорректный PDF')
        reader=PdfReader(io.BytesIO(data),strict=True)
        if len(reader.pages)>35: raise ValueError('Слишком много страниц')
        parts=[]
        extracted_pages=[(page.extract_text() or '') for page in reader.pages]
        missing=[i for i,t in enumerate(extracted_pages) if len(t.strip())<5]
        if len(missing)>3:
            raise ValueError('Для OCR допускается максимум три сканированные страницы')
        for i,extracted in enumerate(extracted_pages):
            if i in missing:
                from .ocr import scan_pdf_page
                extracted=scan_pdf_page(data,i)
            parts.append(f'Страница {i+1}:\n'+extracted)
        text='\n'.join(parts)
    elif ext in ('.png','.jpg','.jpeg'):
        from .ocr import recognize
        text=recognize(data)
    elif ext=='.docx':
        if 'word/document.xml' not in safe_zip(data): raise ValueError('Некорректный DOCX')
        from docx import Document
        d=Document(io.BytesIO(data))
        lines=[p.text for p in d.paragraphs]
        for table in d.tables:
            for row in table.rows:
                lines.extend(c.text for c in row.cells)
        text='\n'.join(lines)
    elif ext=='.xlsx':
        if 'xl/workbook.xml' not in safe_zip(data): raise ValueError('Некорректный XLSX')
        from openpyxl import load_workbook
        book=load_workbook(io.BytesIO(data),read_only=True,data_only=True,keep_links=False)
        lines=[]
        for sheet in book.worksheets[:5]:
            lines.append('Лист: '+sheet.title)
            for row in sheet.iter_rows(max_row=min(sheet.max_row or 1000,1000),max_col=min(sheet.max_column or 30,30),values_only=True):
                lines.append(' | '.join(str(c)[:160] for c in row if c is not None))
                if sum(len(x) for x in lines)>MAX_TEXT: break
            if sum(len(x) for x in lines)>MAX_TEXT: break
        book.close()
        text='\n'.join(lines)
    else: raise ValueError('Неподдерживаемое расширение')
    return re.sub(r'\x00','',text)[:MAX_TEXT]

def limits():
    if os.name=='posix':
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(640*1024*1024,640*1024*1024))
        resource.setrlimit(resource.RLIMIT_CPU,(28,28))
        resource.setrlimit(resource.RLIMIT_FSIZE,(1024*1024,1024*1024))

if __name__=='__main__':
    try:
        limits()
        payload=json.load(sys.stdin)
        content=base64.b64decode(payload['content'],validate=True)
        print(json.dumps({'text':extract(content,payload['ext'])},ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({'error':str(exc)[:160]},ensure_ascii=False))
        sys.exit(1)
