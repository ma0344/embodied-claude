"""WS-5b — direct weather/temp ask gate, JMA fetch, resolve order."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from presence_ui.gateway.search_prefetch import (
    detect_web_search_intent,
    format_web_search_prefetch_block,
    prefetch_web_search_for_message,
    resolve_web_search_prefetch,
)
from presence_ui.gateway.search_tier import (
    clear_search_cache,
    reset_ws5_cooldown,
    reset_ws5b_cooldown,
    ws5_record_fetch,
    ws5_should_skip_fetch,
    ws5b_record_fetch,
    ws5b_should_skip_fetch,
)
from presence_ui.gateway.weather_api import (
    JMA_AMEDAS_MATSUMOTO,
    JMA_CLASS10_CHUBU,
    JMA_OFFICE_NAGANO,
    format_weather_answer,
    parse_jma_forecast_json,
)
from presence_ui.gateway.ws5_spontaneous import should_spontaneous_fact_check
from presence_ui.gateway.ws5b_weather import (
    extract_region_label,
    extract_ws5b_search_query,
    should_ws5b_weather_prefetch,
)


def _sample_jma_payload() -> list[dict]:
    return [
        {
            "publishingOffice": "長野地方気象台",
            "reportDatetime": "2026-07-15T17:00:00+09:00",
            "timeSeries": [
                {
                    "timeDefines": ["2026-07-15T17:00:00+09:00"],
                    "areas": [
                        {
                            "area": {"name": "中部", "code": JMA_CLASS10_CHUBU},
                            "weathers": ["くもり　一時　雨"],
                        }
                    ],
                },
                {
                    "timeDefines": [
                        "2026-07-16T00:00:00+09:00",
                        "2026-07-16T09:00:00+09:00",
                    ],
                    "areas": [
                        {
                            "area": {"name": "松本", "code": JMA_AMEDAS_MATSUMOTO},
                            "temps": ["24", "34"],
                        }
                    ],
                },
            ],
        }
    ]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("今の松本市、気温何度ぐらい？", True),
        ("松本の天気どう？", True),
        ("外暑い？", True),
        ("気温教えて", True),
        ("今日の予報は？", True),
        ("サッカーおもしろかった", False),
        ("なんで暑いの？", False),  # causal
        ("松本市の様式を調べて", False),  # WS-2
        ("今日、関東で地震があったらしいよ", False),  # WS-5 hearsay, not 5b
        ("おはよう", False),
    ],
)
def test_should_ws5b_weather_prefetch(text: str, expected: bool) -> None:
    assert should_ws5b_weather_prefetch(text) is expected


def test_ws5_hearsay_still_fires_not_broken() -> None:
    assert should_spontaneous_fact_check("今日、関東で地震があったらしいよ") is True
    assert should_ws5b_weather_prefetch("今日、関東で地震があったらしいよ") is False


def test_default_matsumoto_when_region_omitted() -> None:
    label, used_default = extract_region_label("気温何度ぐらい？")
    assert label == "松本"
    assert used_default is True
    q = extract_ws5b_search_query("気温何度ぐらい？")
    assert q.startswith("松本")
    assert "気温" in q or "何度" in q


def test_region_matsumoto_explicit() -> None:
    label, used_default = extract_region_label("今の松本市、気温何度ぐらい？")
    assert label == "松本"
    assert used_default is False


def test_resolve_order_ws2_then_ws5_then_ws5b() -> None:
    ws2 = resolve_web_search_prefetch("松本の気温を調べて")
    assert ws2 is not None
    assert ws2[0] == "ws2"

    ws5 = resolve_web_search_prefetch("天気、今日大雨らしい")
    assert ws5 is not None
    assert ws5[0] == "ws5"

    ws5b = resolve_web_search_prefetch("今の松本市、気温何度ぐらい？")
    assert ws5b is not None
    assert ws5b[0] == "ws5b"
    assert "松本" in ws5b[1]


def test_soccer_ambiguous_does_not_resolve() -> None:
    assert resolve_web_search_prefetch("サッカーおもしろかった") is None
    assert detect_web_search_intent("サッカーおもしろかった") is False


def test_parse_jma_forecast_matsumoto_temps() -> None:
    snap = parse_jma_forecast_json(_sample_jma_payload())
    assert snap is not None
    assert snap.temp_min == "24"
    assert snap.temp_max == "34"
    assert "くもり" in snap.weather_text
    assert JMA_OFFICE_NAGANO in snap.source_url
    answer = format_weather_answer(snap, used_default_region=True)
    assert "松本（前提・地域未指定）" in answer
    assert "24" in answer and "34" in answer


def test_format_ws5b_directive_requires_numbers() -> None:
    block = format_web_search_prefetch_block(
        query="松本 気温",
        answer="松本 気温 最低24℃ / 最高34℃ · 天気:くもり",
        status="ok",
        backend="jma_forecast",
        source="ws5b",
    )
    assert "trigger=ws5b" in block
    assert "answer=松本 気温 最低24℃" in block
    assert "WS-5b" in block
    assert "Do NOT invent temperatures" in block


@pytest.mark.asyncio
async def test_prefetch_ws5b_uses_jma_api(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_search_cache()
    reset_ws5b_cooldown()

    async def _fake_fetch(*, region_label: str = "松本", timeout_sec: float = 8.0):
        from presence_ui.gateway.weather_api import parse_jma_forecast_json

        return parse_jma_forecast_json(_sample_jma_payload(), region_label=region_label)

    serp = AsyncMock(return_value=([], "q", "empty", "brave"))
    monkeypatch.setattr(
        "presence_ui.gateway.weather_api.fetch_jma_matsumoto_weather",
        _fake_fetch,
    )
    monkeypatch.setattr(
        "presence_ui.gateway.search_prefetch.search_with_urls",
        serp,
    )
    note, events, hits, query = await prefetch_web_search_for_message(
        "今の松本市、気温何度ぐらい？"
    )
    assert note is not None
    assert "trigger=ws5b" in note
    assert "backend=jma_forecast" in note
    assert "34" in note
    assert "松本" in query
    assert events[0]["label"] == "天気を確認した"
    serp.assert_not_called()


@pytest.mark.asyncio
async def test_prefetch_ws5b_falls_back_to_serp(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_search_cache()
    reset_ws5b_cooldown()
    from presence_ui.gateway.web_search import SearchHit

    monkeypatch.setattr(
        "presence_ui.gateway.weather_api.fetch_jma_matsumoto_weather",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "presence_ui.gateway.search_prefetch.search_with_urls",
        AsyncMock(
            return_value=(
                [SearchHit(url="https://example.com", title="t", snippet="気温30度")],
                "松本 気温",
                "ok",
                "brave",
            )
        ),
    )
    note, _, _, _ = await prefetch_web_search_for_message("気温何度ぐらい？")
    assert note is not None
    assert "trigger=ws5b" in note
    assert "backend=brave" in note
    assert "前提・地域未指定" in note


def test_ws5b_cooldown_independent_of_ws5(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_search_cache()
    reset_ws5_cooldown()
    reset_ws5b_cooldown()
    monkeypatch.setenv("PRESENCE_WS5_COOLDOWN_SEC", "60")
    monkeypatch.setenv("PRESENCE_WS5B_COOLDOWN_SEC", "60")
    ws5_record_fetch()
    assert ws5_should_skip_fetch("関東 地震") is True
    assert ws5b_should_skip_fetch("松本 気温") is False
    ws5b_record_fetch()
    assert ws5b_should_skip_fetch("松本 気温") is True
    # WS-5 still blocked on its own counter; 5b block does not clear it
    assert ws5_should_skip_fetch("関東 地震") is True


def test_ws5b_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_WS5B_ENABLED", "0")
    assert should_ws5b_weather_prefetch("今の松本市、気温何度ぐらい？") is False
    assert resolve_web_search_prefetch("今の松本市、気温何度ぐらい？") is None
