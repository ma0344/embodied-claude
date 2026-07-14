"""Tests for DOC-READ C: registry, retrieve, and conversation prefetch."""

from __future__ import annotations

import pytest

from presence_ui.gateway import doc_prefetch
from presence_ui.services import doc_read


@pytest.fixture(autouse=True)
def _store(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESENCE_DOC_STORE_DIR", str(tmp_path / "docs"))
    monkeypatch.setenv("PRESENCE_DOC_CHUNK_CHARS", "8000")
    monkeypatch.setenv("PRESENCE_DOC_STICKY_TURNS", "2")
    monkeypatch.setenv("PRESENCE_DOC_INTENT_E4B", "0")


def _pages() -> list[str]:
    return [
        "表紙",
        "はじめに田中康雄\n序文の話",
        "目次\n第一章\n第二章",
        "第一章 甘え\nグループホームの運営と権利について" + ("あ" * 200),
        "第二章 本人のもの\n失敗と自己決定のエピソード" + ("い" * 200),
    ]


def _ingest(monkeypatch, title="テスト本") -> str:
    monkeypatch.setattr(doc_read, "extract_pages", lambda p: (_pages(), title))
    import pathlib

    pdf = pathlib.Path(doc_read.doc_store_dir()).parent / "b.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF fake unique bytes")
    meta, _ = doc_read.ingest_pdf(pdf)
    # give the book a real map so build_doc_context_block has [map]
    doc_read.map_path(meta.doc_id).write_text("# 本の地図\n全体要約", encoding="utf-8")
    return meta.doc_id


def test_query_terms_jp_en():
    terms = doc_read.query_terms("グループホームの ADHD について")
    # JP run may include trailing particles (substring scoring tolerates it)
    assert any(t.startswith("グループホーム") for t in terms)
    assert "adhd" in terms


def test_select_chunks_ranks_relevant(monkeypatch):
    doc_id = _ingest(monkeypatch)
    chunks = doc_read.select_chunks(doc_id, "グループホームの運営と権利", max_chunks=1)
    assert chunks
    assert "グループホーム" in chunks[0].text


def test_select_chunks_empty_query(monkeypatch):
    doc_id = _ingest(monkeypatch)
    assert doc_read.select_chunks(doc_id, "！！！", max_chunks=2) == []


def test_registry_auto_register_and_active(monkeypatch):
    doc_id = _ingest(monkeypatch)
    assert doc_read.active_doc_id() == doc_id
    entries = doc_read.list_registry()
    assert any(e.doc_id == doc_id for e in entries)


def test_resolve_doc_by_text_title_alias(monkeypatch):
    doc_id = _ingest(monkeypatch, title="ADHDの僕がGHを作ったら")
    doc_read.set_doc_title(doc_id, "ADHDの僕がGHを作ったら", aliases=["グループホーム本"])
    assert doc_read.resolve_doc_by_text("この間のグループホーム本の続きだけど") == doc_id
    assert doc_read.resolve_doc_by_text("今日は天気の話") is None


def test_resolve_doc_for_turn_title_then_sticky_decay(monkeypatch):
    doc_id = _ingest(monkeypatch, title="グループホーム本")
    session = "sess-1"

    # 1) title match opens (reason=title), sets sticky TTL=2
    got, reason = doc_prefetch.resolve_doc_for_turn(
        "グループホーム本の話しよ", session, skip_e4b=True
    )
    assert got == doc_id and reason == "title"

    # 2) no cue, sticky continues (reason=sticky), remaining 2→1
    got, reason = doc_prefetch.resolve_doc_for_turn(
        "それでね、どう思う？", session, skip_e4b=True
    )
    assert got == doc_id and reason == "sticky"

    # 3) sticky continues, remaining 1→0
    got, reason = doc_prefetch.resolve_doc_for_turn("うんうん", session, skip_e4b=True)
    assert got == doc_id and reason == "sticky"

    # 4) sticky exhausted → none
    got, reason = doc_prefetch.resolve_doc_for_turn(
        "全然違う話", session, skip_e4b=True
    )
    assert got is None and reason == "none"


def test_resolve_doc_for_turn_cue_uses_active(monkeypatch):
    doc_id = _ingest(monkeypatch, title="無関係タイトルXYZ")
    got, reason = doc_prefetch.resolve_doc_for_turn(
        "さっきの本の続き", "sess-2", skip_e4b=True
    )
    assert got == doc_id and reason == "cue"


def test_has_cue_rejects_honnou_and_bunshou():
    assert doc_prefetch._has_cue("本能に支配されている") is False
    assert doc_prefetch._has_cue("文章を読む") is False
    assert doc_prefetch._has_cue("第一章の話") is True
    assert doc_prefetch._has_cue("さっきの続き") is True


def test_resolve_doc_rashomon_thread_no_candidate(monkeypatch):
    _ingest(monkeypatch, title="ADHDの僕がGHを作ったら")
    text = (
        "うーん、僕は人間のそういう「えぐい」部分が自分の中にある。"
        "極限状態ではなくても、人間はやっぱり動物としての本能に支配されている。"
    )
    got, reason = doc_prefetch.resolve_doc_for_turn(text, "morning-sess", skip_e4b=True)
    assert got is None and reason == "none"


def test_resolve_doc_cue_blocked_without_e4b(monkeypatch):
    doc_id = _ingest(monkeypatch, title="無関係タイトルXYZ")
    got, reason = doc_prefetch.resolve_doc_for_turn("さっきの続き", "sess-cue")
    assert got is None and reason == "none"
    assert doc_read.active_doc_id() == doc_id


def test_resolve_doc_cue_confirmed_with_e4b(monkeypatch):
    from presence_ui.gateway import doc_prefetch_stage

    doc_id = _ingest(monkeypatch, title="無関係タイトルXYZ")
    monkeypatch.setenv("PRESENCE_DOC_INTENT_E4B", "1")
    monkeypatch.setattr(
        "presence_ui.gateway.doc_prefetch_stage.run_doc_intent_confirm",
        lambda **kwargs: doc_prefetch_stage.DocIntentParsed(open_registered_book=True),
    )

    got, reason = doc_prefetch.resolve_doc_for_turn("さっきの続き", "sess-e4b")
    assert got == doc_id and reason == "cue"


def test_resolve_doc_title_blocked_when_hon_gate_rejects(monkeypatch):
    _ingest(monkeypatch, title="グループホーム本")
    monkeypatch.setenv("PRESENCE_DOC_INTENT_E4B", "1")
    monkeypatch.setattr(
        "presence_ui.gateway.doc_prefetch_stage.run_hon_as_book_check",
        lambda **kwargs: False,
    )

    got, reason = doc_prefetch.resolve_doc_for_turn(
        "グループホーム本の話をしよう", "sess-hon"
    )
    assert got is None and reason == "none"


def test_resolve_doc_title_opens_when_hon_and_intent_pass(monkeypatch):
    from presence_ui.gateway import doc_prefetch_stage

    doc_id = _ingest(monkeypatch, title="グループホーム本")
    monkeypatch.setenv("PRESENCE_DOC_INTENT_E4B", "1")
    monkeypatch.setattr(
        "presence_ui.gateway.doc_prefetch_stage.run_hon_as_book_check",
        lambda **kwargs: True,
    )
    monkeypatch.setattr(
        "presence_ui.gateway.doc_prefetch_stage.run_doc_intent_confirm",
        lambda **kwargs: doc_prefetch_stage.DocIntentParsed(open_registered_book=True),
    )

    got, reason = doc_prefetch.resolve_doc_for_turn(
        "グループホーム本の話をしよう", "sess-open"
    )
    assert got == doc_id and reason == "title"


def test_build_doc_context_block(monkeypatch):
    doc_id = _ingest(monkeypatch)
    block = doc_prefetch.build_doc_context_block(doc_id, "グループホームの運営")
    assert block is not None
    assert "[doc_context]" in block
    assert "[map]" in block
    assert "[/doc_context]" in block
    assert "Gateway directive" in block


async def test_prefetch_doc_context_for_turn(monkeypatch):
    _ingest(monkeypatch, title="グループホーム本")
    note, events = await doc_prefetch.prefetch_doc_context_for_turn(
        "グループホーム本の運営の話の続き", session_id="s3"
    )
    assert note is not None
    assert "[doc_context]" in note
    assert events
    # unrelated chatter, no cue, no sticky → nothing
    note2, _ = await doc_prefetch.prefetch_doc_context_for_turn(
        "今日は暑いね", session_id="s-empty"
    )
    assert note2 is None


async def test_prefetch_disabled(monkeypatch):
    _ingest(monkeypatch, title="グループホーム本")
    monkeypatch.setenv("PRESENCE_DOC_CONTEXT", "0")
    note, events = await doc_prefetch.prefetch_doc_context_for_turn(
        "グループホーム本の話", session_id="s4"
    )
    assert note is None and events == []
