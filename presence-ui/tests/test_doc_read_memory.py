"""Tests for DOC-READ D — map/discussion memory persistence."""

from __future__ import annotations

from dataclasses import asdict
from unittest.mock import patch

import pytest

from presence_ui.gateway.deterministic_memory import RememberOutcome
from presence_ui.services import doc_memory, doc_read


@pytest.fixture(autouse=True)
def _store(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESENCE_DOC_STORE_DIR", str(tmp_path / "docs"))
    monkeypatch.setenv("PRESENCE_DOC_MEMORY", "1")


def _sample_map() -> str:
    return (
        "# 本の地図 — テスト本\n\n"
        "- doc_id: `abc`\n"
        "- 10 ページ / 1000 字 / 2 chunk\n\n"
        "## 全体\n"
        "全体の要約テキスト。\n\n"
        "## 章ごと\n"
        "### 第一章\n"
        "第一章 gist。\n"
    )


def test_gist_for_memory_starts_at_overall():
    gist = doc_memory.gist_for_memory(_sample_map(), max_chars=5000)
    assert gist.startswith("## 全体")
    assert "第一章 gist" in gist
    assert "# 本の地図" not in gist


def test_gist_for_memory_trims():
    long_body = "## 全体\n" + ("あ" * 5000)
    gist = doc_memory.gist_for_memory(long_body, max_chars=100)
    assert len(gist) <= 101
    assert gist.endswith("…")


@patch("presence_ui.services.doc_memory.persist_remember_intent")
def test_remember_book_map_persists_and_flags(mock_persist, tmp_path):
    doc_id = "mapdoc01"
    doc_read.doc_dir(doc_id).mkdir(parents=True)
    doc_read.map_path(doc_id).write_text(_sample_map(), encoding="utf-8")
    doc_read.register_doc(doc_id, title="テスト本", aliases=["別名"])

    mock_persist.return_value = RememberOutcome(ok=True, content="x", memory_id="mem-a-1")

    outcome = doc_memory.remember_book_map(doc_id)
    assert outcome.ok
    assert outcome.memory_id == "mem-a-1"
    mock_persist.assert_called_once()
    intent = mock_persist.call_args[0][0]
    assert intent.category == "memory"
    assert "doc_id: mapdoc01" in intent.content
    assert "テスト本" in intent.content
    assert "別名" in intent.content

    entry = doc_read.get_doc_registry_entry(doc_id)
    assert entry["memory_map_id"] == "mem-a-1"
    assert entry.get("memory_map_at")

    mock_persist.reset_mock()
    dup = doc_memory.remember_book_map(doc_id)
    assert dup.duplicate
    mock_persist.assert_not_called()


@patch("presence_ui.services.doc_memory.persist_remember_intent")
def test_remember_book_discussed_once(mock_persist):
    doc_id = "discdoc1"
    doc_read.register_doc(doc_id, title="議論本")

    mock_persist.return_value = RememberOutcome(ok=True, content="y", memory_id="mem-b-1")

    first = doc_memory.remember_book_discussed(doc_id, cue="続きだけど感想を")
    assert first.ok
    intent = mock_persist.call_args[0][0]
    assert intent.category == "conversation"
    assert "議論した本" in intent.content
    assert "続きだけど感想を" in intent.content

    mock_persist.reset_mock()
    second = doc_memory.remember_book_discussed(doc_id, cue="もう一回")
    assert second.duplicate
    mock_persist.assert_not_called()


@patch("presence_ui.services.doc_memory.persist_remember_intent")
@pytest.mark.asyncio
async def test_build_map_triggers_remember_a(mock_persist, tmp_path, monkeypatch):
    monkeypatch.setattr(doc_read, "extract_pages", lambda p: (["第一章\n本文"], "テスト本"))
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-fake")
    meta, _ = doc_read.ingest_pdf(pdf)

    mock_persist.return_value = RememberOutcome(ok=True, content="z", memory_id="mem-map")

    async def fake_summary(heading, text):
        return f"要約:{heading}"

    async def fake_overall(title, joined):
        return "全体要約"

    await doc_read.build_map(meta.doc_id, summarize=fake_summary, overall=fake_overall)
    mock_persist.assert_called_once()
    entry = doc_read.get_doc_registry_entry(meta.doc_id)
    assert entry.get("memory_map_id") == "mem-map"


@patch("presence_ui.services.doc_memory.remember_book_discussed")
@pytest.mark.asyncio
async def test_prefetch_triggers_remember_b(mock_discussed):
    from presence_ui.gateway import doc_prefetch

    doc_id = "pref01"
    doc_read.doc_dir(doc_id).mkdir(parents=True)
    doc_read.map_path(doc_id).write_text(_sample_map(), encoding="utf-8")
    meta = doc_read.DocMeta(
        doc_id=doc_id,
        source_path="book.pdf",
        title="テスト本",
        page_count=10,
        total_chars=1000,
        chunk_count=1,
        created_at="2026-07-08T00:00:00+09:00",
    )
    doc_read.meta_path(doc_id).write_text(
        __import__("json").dumps(asdict(meta), ensure_ascii=False),
        encoding="utf-8",
    )
    chunk = doc_read.DocChunk(
        doc_id=doc_id,
        chunk_id=0,
        heading="第一章",
        part=0,
        page_start=0,
        page_end=0,
        char_count=10,
        text="本文",
    )
    with doc_read.chunks_path(doc_id).open("w", encoding="utf-8") as handle:
        handle.write(__import__("json").dumps(asdict(chunk), ensure_ascii=False) + "\n")
    doc_read.register_doc(doc_id, title="テスト本", aliases=["本"])

    mock_discussed.return_value = RememberOutcome(ok=True, content="", memory_id="b1")

    note, _ = await doc_prefetch.prefetch_doc_context_for_turn(
        "テスト本の続きだけど",
        session_id="sess-1",
    )
    assert note is not None
    assert "[doc_context]" in note
    mock_discussed.assert_called_once()
    assert mock_discussed.call_args.kwargs["cue"] == "テスト本の続きだけど"
