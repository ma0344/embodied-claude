"""Tests for WS-2d PDF text extraction (services.pdf_extract + url_prefetch wiring)."""

from __future__ import annotations

import pytest

from presence_ui.gateway import url_prefetch
from presence_ui.services import pdf_extract

fitz = pytest.importorskip("fitz")


def _make_text_pdf(body: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), body)
    data = doc.tobytes()
    doc.close()
    return data


def _make_blank_pdf() -> bytes:
    doc = fitz.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    return data


def test_extract_text_from_bytes_ok():
    data = _make_text_pdf("Koyori reads the neighbor report about the garden")
    result = pdf_extract.extract_text_from_bytes(data)
    assert result.status == "ok"
    assert "neighbor report" in result.text
    assert result.pages_total == 1


def test_extract_text_from_bytes_scanned_when_no_text():
    result = pdf_extract.extract_text_from_bytes(_make_blank_pdf())
    assert result.status == "scanned"
    assert result.text == ""


def test_extract_text_from_bytes_rejects_non_pdf():
    result = pdf_extract.extract_text_from_bytes(b"not a pdf at all")
    assert result.status == "failed"


def test_extract_text_from_bytes_empty():
    assert pdf_extract.extract_text_from_bytes(b"").status == "empty"


def test_extract_text_from_path_allowed(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESENCE_PDF_ALLOW_DIRS", str(tmp_path))
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(_make_text_pdf("Local path extraction sample body"))
    result = pdf_extract.extract_text_from_path(pdf_path)
    assert result.status == "ok"
    assert "extraction sample" in result.text


def test_extract_text_from_path_not_allowed(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setenv("PRESENCE_PDF_ALLOW_DIRS", str(allowed))
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(_make_text_pdf("should not be read"))
    result = pdf_extract.extract_text_from_path(outside)
    assert result.status == "not_allowed"


def test_extract_text_from_path_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESENCE_PDF_ALLOW_DIRS", str(tmp_path))
    result = pdf_extract.extract_text_from_path(tmp_path / "missing.pdf")
    assert result.status == "not_found"


def test_disabled_flag(monkeypatch):
    monkeypatch.setenv("PRESENCE_PDF_EXTRACT", "0")
    assert pdf_extract.extract_text_from_bytes(_make_text_pdf("x")).status == "disabled"


@pytest.mark.parametrize(
    "message,expected",
    [
        ('読んで "C:\\Users\\ma\\Downloads\\foo.pdf"', ["C:\\Users\\ma\\Downloads\\foo.pdf"]),
        ("見て C:\\docs\\paper.pdf よろしく", ["C:\\docs\\paper.pdf"]),
        ("file:///C:/tmp/report.pdf を読んで", ["C:/tmp/report.pdf"]),
        ("これは普通の文章です", []),
        ("画像は C:\\img\\a.png だけ", []),
    ],
)
def test_extract_pdf_paths_from_message(message, expected):
    assert url_prefetch.extract_pdf_paths_from_message(message) == expected


def test_extract_pdf_paths_dedup():
    msg = 'A "C:\\a\\x.pdf" and again C:\\a\\x.pdf'
    assert url_prefetch.extract_pdf_paths_from_message(msg) == ["C:\\a\\x.pdf"]


async def test_fetch_local_pdf_excerpt_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESENCE_PDF_ALLOW_DIRS", str(tmp_path))
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(_make_text_pdf("Garden watering schedule for neighbors summer"))
    excerpt, status = await url_prefetch.fetch_local_pdf_excerpt(
        str(pdf_path), query_terms_list=["garden"]
    )
    assert status == "pdf_ok"
    assert "Garden watering" in excerpt


async def test_fetch_local_pdf_excerpt_not_allowed(tmp_path, monkeypatch):
    allowed = tmp_path / "ok"
    allowed.mkdir()
    monkeypatch.setenv("PRESENCE_PDF_ALLOW_DIRS", str(allowed))
    outside = tmp_path / "nope.pdf"
    outside.write_bytes(_make_text_pdf("secret"))
    excerpt, status = await url_prefetch.fetch_local_pdf_excerpt(str(outside))
    assert status == "pdf_not_allowed"
    assert excerpt == ""


def test_format_block_pdf_ok_includes_excerpt():
    block = url_prefetch.format_url_prefetch_block(
        url="C:\\a\\x.pdf",
        excerpt="body text about the garden",
        status="pdf_ok",
        source="local_pdf",
    )
    assert "excerpt=body text about the garden" in block
    assert "PDF document excerpt" in block


def test_format_block_pdf_scanned_warns():
    block = url_prefetch.format_url_prefetch_block(
        url="http://x/y.pdf",
        excerpt="",
        status="pdf_scanned",
        source="pasted",
    )
    assert "scan" in block.lower()
