"""Tests for MEM-8h-B memory retrieve route classification."""

from __future__ import annotations

import pytest

from interaction_orchestrator_mcp.memory_retrieve_route import (
    allows_compose_recall_stage2,
    allows_memory_bridge,
    classify_memory_retrieve_route,
    looks_like_stock_calendar_schedule_query,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("明日の予定って何か入ってたっけ？", True),
        ("明後日の予定は？", True),
        ("今日のスケジュール教えて", True),
        ("梅干し作ろうかな", False),
        ("ねっとわん いつ", False),
    ],
)
def test_stock_calendar_schedule_query(text: str, expected: bool) -> None:
    assert looks_like_stock_calendar_schedule_query(text) is expected


def test_calendar_read_blocks_memory_bridge() -> None:
    route = classify_memory_retrieve_route("明日の予定は？")
    assert route == "calendar_read"
    assert not allows_memory_bridge(route)
    assert not allows_compose_recall_stage2(route)


def test_future_commitment_not_bridge() -> None:
    route = classify_memory_retrieve_route("じゃぁ、明日は朝から梅の実の収穫をする")
    assert route == "future_commitment"
    assert not allows_memory_bridge(route)


def test_umeboshi_is_memory_bridge_route() -> None:
    route = classify_memory_retrieve_route("そっか、梅干しづくりをしようかな")
    assert route == "memory_bridge"
    assert allows_memory_bridge(route)


def test_recall_utterance_route() -> None:
    route = classify_memory_retrieve_route(
        "煎餅のこと覚えてる？",
        is_recall_utterance=True,
    )
    assert route == "recall_utterance"
    assert not allows_memory_bridge(route)
    assert allows_compose_recall_stage2(route)


def test_entity_temporal_allows_stage2() -> None:
    route = classify_memory_retrieve_route("ねっとわん いつ")
    assert route == "compose_default"
    assert allows_compose_recall_stage2(route)


def test_chitchat_skips_extra_recall() -> None:
    route = classify_memory_retrieve_route("おはよう")
    assert route == "chitchat"
    assert not allows_compose_recall_stage2(route)
