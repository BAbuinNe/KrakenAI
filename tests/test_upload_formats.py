"""Only editable office and UTF-8 text documents are accepted for input."""
import pytest
from fastapi import HTTPException
from app.main import validate_upload
from app.parser_worker import extract


def test_utf8_txt_and_bom():
    assert validate_upload("terms.txt", "Цена 85000 руб.".encode("utf-8")) == ".txt"
    assert extract("ТЗ: 16 ГБ\n".encode("utf-8-sig"), ".txt").strip() == "ТЗ: 16 ГБ"


@pytest.mark.parametrize("name,data", [
    ("image.png", b"\x89PNG\r\n\x1a\nwhatever"),
    ("scan.jpg", b"\xff\xd8\xffanything"),
    ("file.pdf", b"%PDF-1.7\n"),
    ("script.exe", b"MZ.."),
])
def test_disallowed_formats(name,data):
    with pytest.raises(HTTPException) as exc:
        validate_upload(name,data)
    assert exc.value.status_code == 400


@pytest.mark.parametrize("data", [b"\xff\xfeX", b"\x00a", b"\x89PNG\r\n\x1a\n"])
def test_txt_must_be_utf8_text(data):
    with pytest.raises(HTTPException):
        validate_upload("text.txt", data)


def test_office_zip_magic_validation():
    assert validate_upload("terms.docx", b"PK\x03\x04payload") == ".docx"
    assert validate_upload("prices.xlsx", b"PK\x03\x04payload") == ".xlsx"
    with pytest.raises(HTTPException):
        validate_upload("terms.docx",b"not a zip")
