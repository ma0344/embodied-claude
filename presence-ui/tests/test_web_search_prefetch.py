"""WS-2a/2b — web search prefetch and Brave backend."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from presence_ui.gateway import social_chat
from presence_ui.gateway.search_prefetch import (
    extract_search_query,
    format_web_search_prefetch_block,
    prefetch_web_search_for_message,
    web_search_for_message,
)
from presence_ui.gateway.user_intent import resolve_user_intent
from presence_ui.gateway.web_search import SearchHit, brave_web_search, search_with_urls
from presence_ui.services.llm import build_gateway_stable_append
from test_social_chat import _minimal_ctx, _minimal_plan


@pytest.mark.parametrize(
    "text,expected_substr",
    [
        ("松本市の請求様式ってオンラインのどこかにあるか調べてもらえる？", "松本市"),
        ("ネットで cardiovascular AI 調べて", "cardiovascular AI"),
    ],
)
def test_extract_search_query(text: str, expected_substr: str) -> None:
    q = extract_search_query(text)
    assert expected_substr in q
    assert len(q) <= 120


def test_resolve_user_intent_wants_web_search() -> None:
    intent = resolve_user_intent("松本市の様式を調べて")
    assert intent.wants_web_search is True
    assert resolve_user_intent("こんにちは").wants_web_search is False


def test_format_web_search_prefetch_empty_is_honest() -> None:
    block = format_web_search_prefetch_block(
        query="松本市 地域生活支援事業 日中一時 請求様式",
        status="empty",
    )
    assert "[web_search_prefetch]" in block
    assert "status=empty" in block
    assert "Do NOT invent" in block


def test_format_web_search_prefetch_urls() -> None:
    block = format_web_search_prefetch_block(
        query="松本市 請求様式",
        hits=[
            SearchHit(
                url="https://www.city.matsumoto.nagano.jp/soshiki/61/194124.html",
                title="地域生活支援事業",
                snippet="事業者向け資料",
            )
        ],
        status="ok",
        backend="brave",
    )
    assert "backend=brave" in block
    assert "1. https://www.city.matsumoto.nagano.jp" in block
    assert "地域生活支援事業" in block


@pytest.mark.asyncio
async def test_brave_web_search_parses_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-key")

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "web": {
                    "results": [
                        {
                            "url": "https://example.com/form",
                            "title": "Example form",
                            "description": "A sample page",
                        }
                    ]
                }
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None, headers=None):
            assert headers["X-Subscription-Token"] == "test-key"
            assert headers["Cache-Control"] == "no-cache"
            return FakeResponse()

    monkeypatch.setattr("presence_ui.gateway.web_search.httpx.AsyncClient", lambda **kw: FakeClient())
    hits = await brave_web_search("松本市 請求様式")
    assert len(hits) == 1
    assert hits[0].url == "https://example.com/form"


@pytest.mark.asyncio
async def test_search_with_urls_prefers_brave(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-key")
    hit = SearchHit(url="https://example.com", title="t", snippet="s")
    monkeypatch.setattr(
        "presence_ui.gateway.web_search.brave_web_search",
        AsyncMock(return_value=[hit]),
    )
    monkeypatch.setattr(
        "presence_ui.gateway.web_search.ddg_instant_answer",
        AsyncMock(return_value=("should not use", "q")),
    )
    hits, used, status, backend = await search_with_urls("松本市 請求様式")
    assert hits == [hit]
    assert status == "ok"
    assert backend == "brave"
    assert used == "松本市 請求様式"


@pytest.mark.asyncio
async def test_web_search_for_message_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "presence_ui.gateway.search_prefetch.search_with_urls",
        AsyncMock(return_value=([], "松本市 請求様式", "empty", "brave")),
    )
    hits, used, status, backend = await web_search_for_message("松本市 請求様式")
    assert hits == []
    assert used == "松本市 請求様式"
    assert status == "empty"
    assert backend == "brave"


@pytest.mark.asyncio
async def test_prefetch_web_search_for_message_skips_casual() -> None:
    note, events, hits, query = await prefetch_web_search_for_message("おはよう")
    assert note is None
    assert events == []
    assert hits == []
    assert query == ""


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


def test_intercept_includes_web_search_prefetch(
    mock_stores: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PRESENCE_KV_STABLE_APPEND", "1")
    prefetch = format_web_search_prefetch_block(
        query="松本市 請求様式",
        status="empty",
    )
    result = social_chat.intercept_chat_request(
        payload={"message": "松本市の様式を調べて", "sessionId": "sess-ws"},
        person_id="ma",
        web_search_prefetch=prefetch,
    )
    assert result.forward is True
    msg = result.payload["message"]
    assert "[web_search_prefetch]" in msg
    assert "松本市の様式を調べて" in msg
    assert msg.index("松本市の様式を調べて") < msg.index("[web_search_prefetch]")
    assert result.payload["appendSystemPrompt"] == build_gateway_stable_append()
    assert "WebSearch/WebFetch" in msg


@pytest.mark.integration
@pytest.mark.asyncio
async def test_brave_matsumoto_query_live(monkeypatch: pytest.MonkeyPatch) -> None:
    """Manual regression — requires BRAVE_SEARCH_API_KEY in presence-ui.local.env."""
    from presence_ui.repo_env import load_repo_env

    load_repo_env(force=True)
    if not __import__("os").environ.get("BRAVE_SEARCH_API_KEY"):
        pytest.skip("BRAVE_SEARCH_API_KEY not set")

    hits, _, status, backend = await search_with_urls(
        "松本市 地域生活支援事業 日中一時 請求様式"
    )
    assert backend == "brave"
    assert status == "ok"
    assert hits
    urls = " ".join(hit.url for hit in hits)
    assert "city.matsumoto.nagano.jp" in urls
