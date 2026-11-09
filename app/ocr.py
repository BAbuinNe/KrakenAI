"""Offline OCR for bounded PNG/JPEG and scanned PDF pages.
Not a complete malware sandbox. All OCR work runs in a limited parser process.
"""
from __future__ import annotations
import io
import os
import subprocess  # nosec B404: fixed binary, no shell, bounded input
from PIL import Image, ImageOps

MAX_IMAGE_PIXELS=16_000_000
Image.MAX_IMAGE_PIXELS=MAX_IMAGE_PIXELS

def _rasterize(data:bytes)->bytes:
    with Image.open(io.BytesIO(data)) as original:
        if original.width*original.height>MAX_IMAGE_PIXELS:
            raise ValueError('Изображение слишком большое')
        original.load()
        image=ImageOps.exif_transpose(original).convert('RGB')
        image.thumbnail((2200,2200))
        out=io.BytesIO()
        image.save(out,format='PNG',optimize=False)
        return out.getvalue()

def recognize(data:bytes)->str:
    raster=_rasterize(data)
    try:
        result=subprocess.run(  # nosec B603: fixed executable and flags, no shell
            ['tesseract','stdin','stdout','-l','rus+eng','--psm','3'],
            input=raster,capture_output=True,timeout=9,check=False,
            env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'OMP_THREAD_LIMIT':'1','LANG':'C.UTF-8'}
        )
    except (FileNotFoundError,subprocess.TimeoutExpired):
        raise ValueError('Локальный OCR недоступен или превышен лимит времени')
    if result.returncode:
        raise ValueError('Не удалось распознать изображение')
    return result.stdout.decode('utf-8',errors='replace')[:15000]

def scan_pdf_page(data:bytes,index:int)->str:
    import fitz
    with fitz.open(stream=data,filetype='pdf') as document:
        if not 0<=index<document.page_count:
            raise ValueError('Страница PDF не найдена')
        page=document[index]
        area=max(page.rect.width*page.rect.height,1)
        zoom=min(1.8,(MAX_IMAGE_PIXELS/area)**.5)
        pixmap=page.get_pixmap(matrix=fitz.Matrix(zoom,zoom),alpha=False,colorspace=fitz.csRGB)
        return recognize(pixmap.tobytes('png'))
