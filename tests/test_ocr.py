"""Offline OCR smoke test with synthetic documents."""
import io
import shutil
import pytest
from PIL import Image,ImageDraw,ImageFont
from app.parser_worker import extract
from app.main import validate_upload

@pytest.mark.skipif(shutil.which('tesseract') is None,reason='OCR not installed')
def test_jpeg_and_scanned_pdf_ocr():
    im=Image.new('RGB',(1100,360),'white')
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',54)
    ImageDraw.Draw(im).text((50,100),'Мощность 5 кВт',font=font,fill='black')
    jpg=io.BytesIO();im.save(jpg,'JPEG',quality=94)
    assert validate_upload('scan.jpg',jpg.getvalue())=='.jpg'
    assert len(extract(jpg.getvalue(),'.jpg').strip())>7
    scanned_pdf=io.BytesIO();im.save(scanned_pdf,'PDF',resolution=130)
    assert len(extract(scanned_pdf.getvalue(),'.pdf').strip())>7

@pytest.mark.parametrize('filename,body',[('bad.png',b'hello'),('bad.jpeg',b'%PDF-1.2'),('bad.docx',b'notoffice')])
def test_wrong_magic_bytes_rejected(filename,body):
    from fastapi import HTTPException
    with pytest.raises(HTTPException):validate_upload(filename,body)
