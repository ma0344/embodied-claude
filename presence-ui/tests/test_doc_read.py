"""Tests for DOC-READ ingest (A) + map (B)."""

from __future__ import annotations

import pytest

from presence_ui.services import doc_read


@pytest.fixture(autouse=True)
def _store(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESENCE_DOC_STORE_DIR", str(tmp_path / "docs"))
    monkeypatch.setenv("PRESENCE_DOC_CHUNK_CHARS", "8000")
    monkeypatch.setenv("PRESENCE_DOC_CHUNK_OVERLAP", "200")


def _book_pages() -> list[str]:
    # page0 front matter, page1 はじめに, page2 目次(TOC), then real chapters
    return [
        "本文テキスト\n表紙のようなページ",
        "はじめに田中康雄\nこの本を手にとって……",
        "目次\nはじめに 田中康雄\nプロローグ\n第一章 甘え\n第二章 本人のもの\n第三章 ハッピー",
        "プロローグ\n当事者であり支援者である僕が抱える気持ちの悪さ……",
        "第一章 つい障害に甘えてしまう僕ら\n" + ("本文" * 50),
        "第二章 本人のものは本人のもの\n" + ("内容" * 50),
        "第三章 本人も支援者もハッピーでありたい\n" + ("結び" * 50),
    ]


def test_doc_id_stable():
    a = doc_read.doc_id_for_bytes(b"hello world")
    b = doc_read.doc_id_for_bytes(b"hello world")
    c = doc_read.doc_id_for_bytes(b"different")
    assert a == b
    assert a != c
    assert len(a) == 16


def test_detect_chapters_skips_toc():
    boundaries = doc_read.detect_chapters(_book_pages())
    headings = [h for h, _ in boundaries]
    pages = [p for _, p in boundaries]
    # はじめに(p1), プロローグ(p3), 第一章(4), 第二章(5), 第三章(6). TOC page2 skipped.
    assert headings[0].startswith("はじめに")
    assert any(h.startswith("プロローグ") for h in headings)
    assert sum(1 for h in headings if h.startswith("第") and "章" in h) == 3
    assert 2 not in pages  # TOC page never becomes a boundary
    assert pages == sorted(pages)


def test_detect_chapters_skips_toc_continuation():
    """TOC continuation pages (≥2 short markers, no 目次 word) are skipped too."""
    pages = [
        "表紙",
        "目次\n第一章\n第二章",
        "エピローグ短\nおわりに短",  # 2 markers — skip like p4 of real book
        "第一章\n本文",
    ]
    boundaries = doc_read.detect_chapters(pages)
    assert len(boundaries) == 1
    assert boundaries[0][0].startswith("第一章")  # ordered


def test_detect_chapters_first_occurrence_wins():
    # 第一章 appears in TOC(excluded) and body — only the body page is a boundary, once
    boundaries = doc_read.detect_chapters(_book_pages())
    ch1 = [p for h, p in boundaries if h.startswith("第一章")]
    assert ch1 == [4]


def test_build_chunks_has_front_and_chapters():
    chunks = doc_read.build_chunks(_book_pages(), "docid0")
    headings = [c.heading for c in chunks]
    assert headings[0] == "（前付け）"
    assert any(h.startswith("第一章") for h in headings)
    assert all(c.doc_id == "docid0" for c in chunks)
    assert [c.chunk_id for c in chunks] == list(range(len(chunks)))


def test_build_chunks_splits_long(monkeypatch):
    monkeypatch.setenv("PRESENCE_DOC_CHUNK_CHARS", "1000")
    monkeypatch.setenv("PRESENCE_DOC_CHUNK_OVERLAP", "100")
    pages = ["第一章 長い章\n" + ("あ" * 5000)]
    chunks = doc_read.build_chunks(pages, "d")
    ch1 = [c for c in chunks if c.heading.startswith("第一章")]
    assert len(ch1) > 1
    assert [c.part for c in ch1] == list(range(1, len(ch1) + 1))


def test_ingest_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(doc_read, "extract_pages", lambda p: (_book_pages(), "テスト本"))
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake bytes for id")
    meta, chunks = doc_read.ingest_pdf(pdf)

    assert meta.title == "テスト本"
    assert meta.page_count == 7
    assert meta.chunk_count == len(chunks)
    assert doc_read.meta_path(meta.doc_id).is_file()

    loaded_meta = doc_read.load_meta(meta.doc_id)
    loaded_chunks = doc_read.load_chunks(meta.doc_id)
    assert loaded_meta.doc_id == meta.doc_id
    assert len(loaded_chunks) == len(chunks)
    assert loaded_chunks[0].heading == chunks[0].heading


async def test_build_map_with_stub(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESENCE_DOC_MEMORY", "0")
    monkeypatch.setattr(doc_read, "extract_pages", lambda p: (_book_pages(), "テスト本"))
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    meta, _ = doc_read.ingest_pdf(pdf)

    async def fake_summary(heading, text):
        return f"[要約:{heading[:6]}]"

    async def fake_overall(title, joined):
        return f"[全体:{title}]"

    body = await doc_read.build_map(meta.doc_id, summarize=fake_summary, overall=fake_overall)
    assert "本の地図" in body
    assert "[全体:テスト本]" in body
    assert "[要約:" in body
    assert doc_read.map_path(meta.doc_id).is_file()


def test_rewrite_map_display_title_prefers_registry(tmp_path, monkeypatch):
    doc_id = "titlefix"
    doc_read.doc_dir(doc_id).mkdir(parents=True)
    doc_read.map_path(doc_id).write_text("# 本の地図 — !L\n\n## 全体\nok\n", encoding="utf-8")
    doc_read.register_doc(doc_id, title="人間タイトル")
    body = doc_read.rewrite_map_display_title(doc_id)
    assert body is not None
    assert body.startswith("# 本の地図 — 人間タイトル\n")
    assert "!L" not in body.splitlines()[0]


def test_set_doc_title_rewrites_map_heading():
    doc_id = "titlefix2"
    doc_read.doc_dir(doc_id).mkdir(parents=True)
    doc_read.map_path(doc_id).write_text("# 本の地図 — garbage\n\n## 全体\nok\n", encoding="utf-8")
    doc_read.set_doc_title(doc_id, "ADHDの僕がグループホームを作ったら")
    assert doc_read.load_map(doc_id).startswith("# 本の地図 — ADHDの僕がグループホームを作ったら\n")


async def test_build_map_missing_doc():
    with pytest.raises(FileNotFoundError):
        await doc_read.build_map("nope", summarize=None)


def test_extract_pages_plumbing(tmp_path):
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello book body text")
    pdf = tmp_path / "ascii.pdf"
    doc.save(str(pdf))
    doc.close()
    pages, title = doc_read.extract_pages(pdf)
    assert len(pages) == 1
    assert "Hello book" in pages[0]
    assert isinstance(title, str)
