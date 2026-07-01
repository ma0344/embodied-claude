"""L0–L2 tiered search — cache, direct URLs, WS-5 cooldown."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from presence_ui.gateway.search_prefetch import format_web_search_prefetch_block
from presence_ui.gateway.search_tier import (
    clear_search_cache,
    direct_url_candidates,
    get_cached,
    normalize_query_key,
    reset_ws5_cooldown,
    store_cache,
    tiered_search,
    ws5_cooldown_sec,
    ws5_record_fetch,
    ws5_should_skip_fetch,
)
from presence_ui.gateway.web_search import SearchHit


def test_normalize_query_key_collapses_whitespace() -> None:
    assert normalize_query_key("  沖縄   梅雨  ") == "沖縄 梅雨"


def test_direct_url_candidates_tsuyu() -> None:
    urls = direct_url_candidates("沖縄 梅雨")
    assert urls
    assert "jma.go.jp" in urls[0]
    assert "tsuyu" in urls[0]


def test_format_ws5_prefetch_requires_surface_grounding() -> None:
    block = format_web_search_prefetch_block(
        query="沖縄 梅雨",
        hits=[SearchHit(url="https://www.data.jma.go.jp/", title="t", snippet="明け")],
        status="ok",
        backend="direct_url",
        source="ws5",
    )
    assert "trigger=ws5" in block
    assert "Open your reply with at least one concrete fact" in block
    assert "never looked" in block


@pytest.mark.asyncio
async def test_tiered_search_uses_l0_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_search_cache()
    hit = SearchHit(url="https://example.com", title="cached", snippet="s")
    store_cache("沖縄 梅雨", [hit], "沖縄 梅雨", "ok", "direct_url")
    api = AsyncMock(return_value=([], "q", "empty", "brave"))
    monkeypatch.setattr("presence_ui.gateway.web_search.search_api_backends", api)
    hits, used, status, backend = await tiered_search("沖縄 梅雨")
    assert hits == [hit]
    assert status == "ok"
    assert backend == "cache:direct_url"
    api.assert_not_called()


@pytest.mark.asyncio
async def test_tiered_search_l2_before_api(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_search_cache()
    hit = SearchHit(url="https://www.data.jma.go.jp/", title="jma", snippet="梅雨明け")
    monkeypatch.setattr(
        "presence_ui.gateway.search_tier.fetch_direct_url_hits",
        AsyncMock(return_value=[hit]),
    )
    api = AsyncMock(return_value=([], "q", "empty", "brave"))
    monkeypatch.setattr("presence_ui.gateway.web_search.search_api_backends", api)
    hits, _, status, backend = await tiered_search("沖縄 梅雨")
    assert hits == [hit]
    assert status == "ok"
    assert backend == "direct_url"
    api.assert_not_called()
    assert get_cached("沖縄 梅雨") is not None


def test_ws5_cooldown_blocks_then_allows(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_search_cache()
    reset_ws5_cooldown()
    monkeypatch.setenv("PRESENCE_WS5_COOLDOWN_SEC", "60")
    ws5_record_fetch()
    assert ws5_should_skip_fetch("関東 地震") is True
    assert ws5_should_skip_fetch("関東 地震") is True
    # Cached query bypasses cooldown
    store_cache("関東 地震", [], "関東 地震", "empty", "brave")
    assert ws5_should_skip_fetch("関東 地震") is False


def test_ws5_cooldown_zero_disables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_WS5_COOLDOWN_SEC", "0")
    ws5_record_fetch()
    assert ws5_cooldown_sec() == 0
    assert ws5_should_skip_fetch("anything") is False
