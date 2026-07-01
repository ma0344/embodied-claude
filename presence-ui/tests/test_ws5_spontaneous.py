"""WS-5 v0 — spontaneous fact-check gate and query building."""

from __future__ import annotations

import pytest

from presence_ui.gateway.search_prefetch import (
    detect_web_search_intent,
    resolve_web_search_prefetch,
)
from presence_ui.gateway.ws5_spontaneous import (
    extract_spontaneous_search_query,
    should_spontaneous_fact_check,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("今日、関東で地震があったらしいよ", True),
        ("あと、沖縄は梅雨が明けたみたい", True),
        ("台風が来てるみたい", True),
        ("天気、今日大雨らしい", True),
        ("サッカーおもしろかった", False),
        ("おはよう", False),
        ("松本市の請求様式を調べて", False),  # WS-2
        ("ねえ、昨日の試合どうだった？", False),
    ],
)
def test_should_spontaneous_fact_check(text: str, expected: bool) -> None:
    assert should_spontaneous_fact_check(text) is expected


def test_extract_spontaneous_query_okinawa_tsuyu() -> None:
    q = extract_spontaneous_search_query("あと、沖縄は梅雨が明けたみたい")
    assert "梅雨" in q
    assert "沖縄" in q


def test_extract_spontaneous_query_earthquake() -> None:
    q = extract_spontaneous_search_query("今日、関東で地震があったらしいよ")
    assert "地震" in q
    assert "関東" in q
    assert "年" in q  # local date appended for 今日


def test_resolve_prefetch_ws5_vs_ws2() -> None:
    ws2 = resolve_web_search_prefetch("松本市の様式を調べて")
    assert ws2 is not None
    assert ws2[0] == "ws2"
    assert "松本市" in ws2[1]
    ws5 = resolve_web_search_prefetch("関東で地震があったらしい")
    assert ws5 is not None
    assert ws5[0] == "ws5"
    assert "地震" in ws5[1]


def test_detect_web_search_intent_includes_ws5() -> None:
    assert detect_web_search_intent("今日、関東で地震があったらしいよ") is True
    assert detect_web_search_intent("おはよう") is False


def test_ws5_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_WS5_ENABLED", "0")
    assert should_spontaneous_fact_check("関東で地震があったらしい") is False
    assert detect_web_search_intent("関東で地震があったらしい") is False
    assert detect_web_search_intent("調べて 地震") is True
