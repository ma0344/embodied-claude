"""WS-2c — URL excerpt prefetch."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from presence_ui.gateway import social_chat
from presence_ui.gateway.url_prefetch import (
    extract_urls_from_message,
    format_url_prefetch_block,
    html_to_text,
    is_excerpt_satisfactory,
    prefetch_urls_for_turn,
    query_terms,
    select_excerpt,
)
from presence_ui.gateway.web_search import SearchHit
from presence_ui.services.llm import build_gateway_stable_append
from test_social_chat import _minimal_ctx, _minimal_plan


def test_extract_urls_from_message() -> None:
    text = "これ見て https://www.city.matsumoto.nagano.jp/soshiki/61/1895.html ね"
    urls = extract_urls_from_message(text)
    assert len(urls) == 1
    assert urls[0].endswith("1895.html")


def test_query_terms_japanese() -> None:
    terms = query_terms("松本市 共同生活援助 体制等状況一覧表")
    assert "共同生活援助" in terms
    assert "体制等状況一覧表" in terms


def test_html_to_text_strips_tags() -> None:
    html = "<html><body><main><h1>Title</h1><p>共同生活援助の一覧</p></main></body></html>"
    text = html_to_text(html)
    assert "共同生活援助" in text
    assert "<p>" not in text


def test_select_excerpt_prefers_matching_lines() -> None:
    text = "header\n" + "filler\n" * 20 + "共同生活援助 体制等状況一覧表 ここ\n" + "tail\n" * 20
    excerpt = select_excerpt(text, ["共同生活援助", "体制等状況一覧表"], max_chars=500)
    assert "共同生活援助" in excerpt
    assert "体制等状況一覧表" in excerpt


def test_is_excerpt_satisfactory_requires_long_term() -> None:
    terms = query_terms("共同生活援助 体制等状況一覧表")
    assert not is_excerpt_satisfactory("介護給付費の一般説明だけ", terms)
    assert is_excerpt_satisfactory(
        "共同生活援助事業所向けの体制等状況一覧表の提出について。" * 3,
        terms,
    )


def test_format_url_prefetch_block() -> None:
    block = format_url_prefetch_block(
        url="https://example.com",
        excerpt="共同生活援助の本文",
        status="ok",
        source="pasted",
    )
    assert "[url_prefetch]" in block
    assert "excerpt=共同生活援助" in block
    assert "ONLY from excerpt" in block


@pytest.mark.asyncio
async def test_prefetch_search_loop_tries_until_match(monkeypatch: pytest.MonkeyPatch) -> None:
    hits = [
        SearchHit(url="https://example.com/1", title="a", snippet=""),
        SearchHit(url="https://example.com/2", title="b", snippet=""),
        SearchHit(url="https://example.com/3", title="c", snippet=""),
    ]
    excerpts = {
        "https://example.com/1": "介護給付費の一般的な説明",
        "https://example.com/2": "届出の案内のみ",
        "https://example.com/3": "共同生活援助 体制等状況一覧表 別紙2-1",
    }

    async def fake_fetch(url: str, *, query_terms_list=None):
        return excerpts.get(url, ""), "ok"

    monkeypatch.setattr("presence_ui.gateway.url_prefetch.fetch_url_excerpt", fake_fetch)
    block, events = await prefetch_urls_for_turn(
        "松本市 共同生活援助 体制等状況一覧表 どこ",
        search_hits=hits,
        search_query="松本市 共同生活援助 体制等状況一覧表",
    )
    assert block is not None
    assert "search_rank=3" in block
    assert "共同生活援助" in block
    assert events


@pytest.mark.asyncio
async def test_prefetch_pasted_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "presence_ui.gateway.url_prefetch.fetch_url_excerpt",
        AsyncMock(return_value=("ページ本文", "ok")),
    )
    block, _ = await prefetch_urls_for_turn(
        "https://www.city.matsumoto.nagano.jp/soshiki/61/1895.html を読んで",
        search_hits=[],
        search_query="",
    )
    assert block is not None
    assert "source=pasted" in block
    assert "1895.html" in block


@pytest.fixture
def mock_stores(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    stores = MagicMock()
    stores.policy_timezone = "Asia/Tokyo"
    stores.social_state.ingest_social_event.return_value = {"event_id": "evt-1"}
    monkeypatch.setattr(social_chat, "get_stores", lambda: stores)
    monkeypatch.setattr(
        social_chat,
        "compose_interaction_context",
        lambda *args, **kwargs: _minimal_ctx(),
    )
    monkeypatch.setattr(
        social_chat,
        "plan_response",
        lambda *args, **kwargs: _minimal_plan(),
    )
    return stores


def test_intercept_includes_url_prefetch(
    mock_stores: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PRESENCE_KV_STABLE_APPEND", "1")
    prefetch = format_url_prefetch_block(
        url="https://example.com",
        excerpt="共同生活援助",
        status="ok",
        source="search_loop",
        attempt=3,
    )
    result = social_chat.intercept_chat_request(
        payload={"message": "調べて", "sessionId": "sess-url"},
        person_id="ma",
        url_prefetch=prefetch,
    )
    msg = result.payload["message"]
    assert "[url_prefetch]" in msg
    assert result.payload["appendSystemPrompt"] == build_gateway_stable_append()
