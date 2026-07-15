"""WS-5c — search offer on fact-gap; pending consent → prefetch."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from test_social_chat import _minimal_plan

from presence_ui.gateway.calendar_pending import CalendarPendingRecord
from presence_ui.gateway.calendar_pending import save_pending as save_cal_pending
from presence_ui.gateway.search_prefetch import (
    format_web_search_prefetch_block,
    prefetch_web_search_for_message,
    resolve_web_search_prefetch,
)
from presence_ui.gateway.user_intent import merge_intent_with_plan, resolve_user_intent
from presence_ui.gateway.web_search import SearchHit
from presence_ui.gateway.ws5c_offer import (
    classify_ws5c_reply,
    clear_pending,
    extract_ws5c_query,
    format_ws5c_offer_block,
    load_pending,
    make_pending,
    save_pending,
    should_ws5c_offer,
    ws5c_enabled,
)


@pytest.fixture
def pending_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "ws5c_pending.json"
    monkeypatch.setattr(
        "presence_ui.gateway.ws5c_offer._pending_path",
        lambda: path,
    )
    return path


def test_should_ws5c_offer_fact_ask() -> None:
    assert should_ws5c_offer("松本市の様式の提出窓口ってどこ？") is True
    assert should_ws5c_offer("円相場っていくら？") is True


def test_should_ws5c_offer_excludes_weather_ws2_phatic() -> None:
    assert should_ws5c_offer("松本の気温、何度？") is False
    assert should_ws5c_offer("松本市の様式を調べて") is False
    assert should_ws5c_offer("おはよう") is False
    assert should_ws5c_offer("なんで暑いの？") is False
    assert should_ws5c_offer("サッカーおもしろかった") is False


def test_ws5c_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_WS5C_ENABLED", "0")
    assert ws5c_enabled() is False
    assert should_ws5c_offer("松本市の様式の提出窓口ってどこ？") is False


def test_extract_ws5c_query_strips() -> None:
    q = extract_ws5c_query("松本市の様式の提出窓口ってどこ？")
    assert "松本" in q
    assert len(q) <= 120
    assert not q.endswith("？")


def test_resolve_miss_does_not_auto_prefetch_for_5c_gate() -> None:
    assert resolve_web_search_prefetch("松本市の様式の提出窓口ってどこ？") is None


@pytest.mark.asyncio
async def test_fact_ask_miss_offers_without_serp(
    pending_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serp = AsyncMock(return_value=([], "q", "empty", "brave"))
    monkeypatch.setattr(
        "presence_ui.gateway.search_prefetch.search_with_urls",
        serp,
    )
    note, events, hits, query = await prefetch_web_search_for_message(
        "松本市の様式の提出窓口ってどこ？",
        person_id="ma",
    )
    assert note is not None
    assert "[ws5c_search_offer]" in note
    assert "status=pending" in note
    assert "調べようか" in note or "look it up" in note.lower()
    assert hits == []
    assert query == ""
    assert events[0]["label"] == "調べるか確認する"
    serp.assert_not_called()
    pending = load_pending(person_id="ma")
    assert pending is not None
    assert pending.kind == "ws5c_offer"
    assert "様式" in pending.suggested_query or "松本" in pending.suggested_query


@pytest.mark.asyncio
async def test_ws2_explicit_no_offer(
    pending_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "presence_ui.gateway.search_prefetch.search_with_urls",
        AsyncMock(
            return_value=(
                [SearchHit(url="https://example.com", title="t", snippet="s")],
                "松本市 様式",
                "ok",
                "brave",
            )
        ),
    )
    note, _, _, _ = await prefetch_web_search_for_message(
        "松本市の様式を調べて",
        person_id="ma",
    )
    assert note is not None
    assert "[web_search_prefetch]" in note
    assert "[ws5c_search_offer]" not in note
    assert "trigger=ws2" in note
    assert load_pending(person_id="ma") is None


@pytest.mark.asyncio
async def test_pending_ok_prefetches_ws5c(
    pending_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = make_pending(
        person_id="ma",
        source_utterance="松本市の様式の提出窓口ってどこ？",
        suggested_query="松本市 様式 提出窓口",
    )
    save_pending(record)
    serp = AsyncMock(
        return_value=(
            [SearchHit(url="https://example.com/form", title="様式", snippet="窓口")],
            "松本市 様式 提出窓口",
            "ok",
            "brave",
        )
    )
    monkeypatch.setattr(
        "presence_ui.gateway.search_prefetch.search_with_urls",
        serp,
    )
    note, events, hits, query = await prefetch_web_search_for_message(
        "OK",
        person_id="ma",
    )
    assert note is not None
    assert "[web_search_prefetch]" in note
    assert "trigger=ws5c" in note
    assert query == "松本市 様式 提出窓口"
    assert hits
    assert events[0]["label"] == "ネットを調べた"
    serp.assert_awaited_once()
    assert load_pending(person_id="ma") is None


@pytest.mark.asyncio
async def test_pending_deny_clears_no_search(
    pending_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    save_pending(
        make_pending(
            person_id="ma",
            source_utterance="円相場っていくら？",
            suggested_query="円相場",
        )
    )
    serp = AsyncMock()
    monkeypatch.setattr(
        "presence_ui.gateway.search_prefetch.search_with_urls",
        serp,
    )
    note, _, hits, query = await prefetch_web_search_for_message(
        "いや",
        person_id="ma",
    )
    assert note is not None
    assert "status=declined" in note
    assert hits == []
    assert query == ""
    serp.assert_not_called()
    assert load_pending(person_id="ma") is None


@pytest.mark.asyncio
async def test_ttl_expire_clears(
    pending_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(timezone.utc)
    past = now - timedelta(seconds=10)
    record = make_pending(
        person_id="ma",
        source_utterance="祝日っていつ？",
        suggested_query="祝日",
    )
    record.created_at = (past - timedelta(seconds=200)).isoformat()
    record.expires_at = past.isoformat()
    save_pending(record)
    assert load_pending(person_id="ma") is None
    assert not pending_dir.is_file() or load_pending(person_id="ma") is None


@pytest.mark.asyncio
async def test_pending_shirabete_uses_stored_query_ws5c(
    pending_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Consent cue 「調べて」 must NOT WS-2-extract itself; use suggested_query."""
    stored = "松本市 様式 提出窓口"
    save_pending(
        make_pending(
            person_id="ma",
            source_utterance="松本市の様式の提出窓口ってどこ？",
            suggested_query=stored,
        )
    )
    serp = AsyncMock(
        return_value=(
            [SearchHit(url="https://example.com/form", title="様式", snippet="窓口")],
            stored,
            "ok",
            "brave",
        )
    )
    monkeypatch.setattr(
        "presence_ui.gateway.search_prefetch.search_with_urls",
        serp,
    )
    note, _, hits, query = await prefetch_web_search_for_message(
        "調べて",
        person_id="ma",
    )
    assert note is not None
    assert "trigger=ws5c" in note
    assert "[ws5c_search_offer]" not in note
    assert query == stored
    assert hits
    serp.assert_awaited_once()
    assert serp.await_args.args[0] == stored
    assert load_pending(person_id="ma") is None


@pytest.mark.asyncio
async def test_no_double_confirm_pending_plus_ws2(
    pending_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Topic+調べて while 5c pending → ignore 5c, WS-2 clears pending and searches cue query."""
    save_pending(
        make_pending(
            person_id="ma",
            source_utterance="松本市の様式の提出窓口ってどこ？",
            suggested_query="松本市 様式 提出窓口",
        )
    )
    serp = AsyncMock(
        return_value=(
            [SearchHit(url="https://example.com", title="t", snippet="s")],
            "円相場",
            "ok",
            "brave",
        )
    )
    monkeypatch.setattr(
        "presence_ui.gateway.search_prefetch.search_with_urls",
        serp,
    )
    note, _, _, query = await prefetch_web_search_for_message(
        "円相場調べて",
        person_id="ma",
    )
    assert note is not None
    assert "[ws5c_search_offer]" not in note
    assert "[web_search_prefetch]" in note
    assert "trigger=ws5c" not in note
    assert "trigger=ws2" in note
    assert "円相場" in query
    assert "様式" not in query
    assert load_pending(person_id="ma") is None


@pytest.mark.asyncio
async def test_calendar_awaiting_blocks_5c_offer(
    pending_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cal_path = tmp_path / "calendar_pending.json"
    monkeypatch.setattr(
        "presence_ui.gateway.calendar_pending._pending_path",
        lambda: cal_path,
    )
    save_cal_pending(
        CalendarPendingRecord(
            person_id="ma",
            status="awaiting_confirm",
            action="create",
            calendar_id="primary",
            topic="研修",
            start_iso="2026-08-18T10:00:00+09:00",
            end_iso="2026-08-18T17:00:00+09:00",
            match_label="",
            event_id=None,
            event_calendar_id=None,
            event_summary=None,
            old_start=None,
            old_end=None,
            missing_fields=[],
            source_utterance="orig",
            confirm_summary_ja="研修を入れる",
            created_at="2026-07-15T10:00:00+09:00",
        )
    )
    serp = AsyncMock()
    monkeypatch.setattr(
        "presence_ui.gateway.search_prefetch.search_with_urls",
        serp,
    )
    note, _, _, _ = await prefetch_web_search_for_message(
        "松本市の様式の提出窓口ってどこ？",
        person_id="ma",
    )
    assert note is None
    serp.assert_not_called()
    assert load_pending(person_id="ma") is None


@pytest.mark.asyncio
async def test_calendar_awaiting_ok_does_not_consume_5c(
    pending_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cal_path = tmp_path / "calendar_pending.json"
    monkeypatch.setattr(
        "presence_ui.gateway.calendar_pending._pending_path",
        lambda: cal_path,
    )
    save_cal_pending(
        CalendarPendingRecord(
            person_id="ma",
            status="awaiting_confirm",
            action="create",
            calendar_id="primary",
            topic="研修",
            start_iso="2026-08-18T10:00:00+09:00",
            end_iso="2026-08-18T17:00:00+09:00",
            match_label="",
            event_id=None,
            event_calendar_id=None,
            event_summary=None,
            old_start=None,
            old_end=None,
            missing_fields=[],
            source_utterance="orig",
            confirm_summary_ja="研修を入れる",
            created_at="2026-07-15T10:00:00+09:00",
        )
    )
    save_pending(
        make_pending(
            person_id="ma",
            source_utterance="松本市の様式の提出窓口ってどこ？",
            suggested_query="松本市 様式 提出窓口",
        )
    )
    serp = AsyncMock()
    monkeypatch.setattr(
        "presence_ui.gateway.search_prefetch.search_with_urls",
        serp,
    )
    note, _, _, _ = await prefetch_web_search_for_message(
        "OK",
        person_id="ma",
    )
    assert note is None or "trigger=ws5c" not in (note or "")
    serp.assert_not_called()
    # 5c pending left for calendar exclusivity (not consumed)
    assert load_pending(person_id="ma") is not None


@pytest.mark.asyncio
async def test_web_search_prefetch_off_disables_5c(
    pending_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_WEB_SEARCH_PREFETCH", "0")
    serp = AsyncMock()
    monkeypatch.setattr(
        "presence_ui.gateway.search_prefetch.search_with_urls",
        serp,
    )
    note, _, _, _ = await prefetch_web_search_for_message(
        "松本市の様式の提出窓口ってどこ？",
        person_id="ma",
    )
    assert note is None
    serp.assert_not_called()
    assert load_pending(person_id="ma") is None


@pytest.mark.asyncio
async def test_unrelated_keeps_pending_for_retry(
    pending_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    save_pending(
        make_pending(
            person_id="ma",
            source_utterance="松本市の様式の提出窓口ってどこ？",
            suggested_query="松本市 様式",
        )
    )
    serp = AsyncMock()
    monkeypatch.setattr(
        "presence_ui.gateway.search_prefetch.search_with_urls",
        serp,
    )
    note, _, _, _ = await prefetch_web_search_for_message(
        "サッカーおもしろかった",
        person_id="ma",
    )
    assert note is None
    serp.assert_not_called()
    assert load_pending(person_id="ma") is not None


@pytest.mark.asyncio
async def test_disabled_env_skips_offer(
    pending_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_WS5C_ENABLED", "0")
    serp = AsyncMock()
    monkeypatch.setattr(
        "presence_ui.gateway.search_prefetch.search_with_urls",
        serp,
    )
    note, _, _, _ = await prefetch_web_search_for_message(
        "松本市の様式の提出窓口ってどこ？",
        person_id="ma",
    )
    assert note is None
    serp.assert_not_called()
    assert load_pending(person_id="ma") is None


def test_classify_ws5c_reply(pending_dir: Path) -> None:
    pending = make_pending(
        person_id="ma",
        source_utterance="料金っていくら？",
        suggested_query="料金",
    )
    assert classify_ws5c_reply("うん", pending) == "accept"
    assert classify_ws5c_reply("調べて", pending) == "accept"
    assert classify_ws5c_reply("うん。お願い", pending) == "accept"
    assert classify_ws5c_reply("うん、お願い", pending) == "accept"
    assert classify_ws5c_reply("うん お願い", pending) == "accept"
    assert classify_ws5c_reply("うんお願い", pending) == "accept"
    assert classify_ws5c_reply("いや", pending) == "decline"
    assert classify_ws5c_reply("ええわ", pending) == "decline"
    assert classify_ws5c_reply("大丈夫", pending) == "decline"
    assert classify_ws5c_reply("今日いい天気やね", pending) == "ignore"


@pytest.mark.asyncio
async def test_pending_un_onegai_prefetches_ws5c(
    pending_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real consent phrasing that previously classified ignore and skipped search."""
    save_pending(
        make_pending(
            person_id="ma",
            source_utterance="松本市の様式の提出窓口ってどこ？",
            suggested_query="松本市 様式 提出窓口",
        )
    )
    serp = AsyncMock(
        return_value=(
            [SearchHit(url="https://example.com/form", title="様式", snippet="窓口")],
            "松本市 様式 提出窓口",
            "ok",
            "brave",
        )
    )
    monkeypatch.setattr(
        "presence_ui.gateway.search_prefetch.search_with_urls",
        serp,
    )
    note, _, hits, query = await prefetch_web_search_for_message(
        "うん。お願い",
        person_id="ma",
    )
    assert note is not None
    assert "trigger=ws5c" in note
    assert query == "松本市 様式 提出窓口"
    assert hits
    serp.assert_awaited_once()
    assert load_pending(person_id="ma") is None


@pytest.mark.asyncio
async def test_pending_ignore_keeps_offer(
    pending_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    save_pending(
        make_pending(
            person_id="ma",
            source_utterance="円相場っていくら？",
            suggested_query="円相場",
        )
    )
    monkeypatch.setattr(
        "presence_ui.gateway.search_prefetch.search_with_urls",
        AsyncMock(),
    )
    note, _, _, _ = await prefetch_web_search_for_message(
        "サッカーおもしろかった",
        person_id="ma",
    )
    # Unrelated chat: no new offer/search; pending stays for retry
    assert note is None
    assert load_pending(person_id="ma") is not None


def test_format_ws5c_offer_block_honesty(pending_dir: Path) -> None:
    record = make_pending(
        person_id="ma",
        source_utterance="選挙っていつ？",
        suggested_query="選挙 いつ",
    )
    block = format_ws5c_offer_block(record)
    assert "[ws5c_search_offer]" in block
    assert "Do NOT invent" in block
    assert "Do NOT claim you already searched" in block


def test_format_ws5c_prefetch_directive() -> None:
    block = format_web_search_prefetch_block(
        query="松本市 様式",
        hits=[SearchHit(url="https://example.com", title="t", snippet="s")],
        status="ok",
        backend="brave",
        source="ws5c",
    )
    assert "trigger=ws5c" in block
    assert "WS-5c" in block
    assert "Do NOT invent Sources" in block


def test_user_intent_action_note_for_offer() -> None:
    intent = resolve_user_intent("松本市の様式の提出窓口ってどこ？")
    effective = merge_intent_with_plan(
        intent=intent,
        plan=_minimal_plan(),
        ws5c_offer_pending=True,
    )
    assert effective.speak_action_note is not None
    assert "ws5c_search_offer" in effective.speak_action_note
    assert "調べようか" in effective.speak_action_note


def test_clear_pending(pending_dir: Path) -> None:
    save_pending(
        make_pending(person_id="ma", source_utterance="料金いくら？", suggested_query="料金")
    )
    assert load_pending(person_id="ma") is not None
    clear_pending(person_id="ma")
    assert load_pending(person_id="ma") is None
