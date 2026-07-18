"""MEM-8h-B — Stage-1 memory retrieve route (bridge / stage-2 guards)."""

from __future__ import annotations

import os
import re
from typing import Literal

from interaction_orchestrator_mcp.recall_query import should_skip_compose_recall

MemoryRetrieveRoute = Literal[
    "chitchat",
    "calendar_read",
    "future_commitment",
    "recall_utterance",
    "memory_bridge",
    "compose_default",
]

# Align with presence_ui.gateway.calendar_prefetch (orchestrator must stay import-light).
_CALENDAR_KEYWORDS = re.compile(
    r"(?:予定|スケジュール|カレンダー|カレンダ)",
    re.I,
)
_SCHEDULE_WHEN = re.compile(
    r"(?:今日|明日|あした|明後日|来週).*(?:予定|スケジュール|何か|何が|あった|ある|空いて|忙し|入って)",
    re.I,
)
_WHEN_SCHEDULE = re.compile(
    r"(?:予定|スケジュール).*(?:今日|明日|あした|明後日|来週)",
    re.I,
)
_FUTURE_MARKERS = re.compile(r"明日|明後日|来週|来月|あした|今夜")
_COMMITMENT_ACTION = re.compile(
    r"(する|行く|行って|収穫|もいで|もぐ|作る|やる|会う|届け|送る|出す|提出|始める|終える)"
)
_HISTORY_Q = re.compile(r"思い出|以前|前に|昔|あの時|あの頃")


def memory_retrieve_route_enabled() -> bool:
    raw = os.getenv("PRESENCE_MEM8H_ROUTE", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def looks_like_stock_calendar_schedule_query(text: str) -> bool:
    """定番の calendar read / 予定確認 — memory bridge · stage-2 temporal 禁止."""
    line = (text or "").strip()
    if not line or len(line) > 500:
        return False
    if _CALENDAR_KEYWORDS.search(line):
        return True
    return bool(_SCHEDULE_WHEN.search(line) or _WHEN_SCHEDULE.search(line))


def looks_like_future_commitment_cue(text: str) -> bool:
    """未来約束っぽい発話 — OL-GATE 側。bridge 禁止（C 前のルール分岐）。"""
    line = (text or "").strip()
    if not line or looks_like_stock_calendar_schedule_query(line):
        return False
    if not _FUTURE_MARKERS.search(line):
        return False
    return bool(_COMMITMENT_ACTION.search(line))


def _bridge_topic_keywords(text: str) -> list[str]:
    from interaction_orchestrator_mcp.memory_adapter import _extract_keywords

    return _extract_keywords(text, max_keywords=6)


def bridge_topic_keywords(text: str) -> list[str]:
    """Keywords for MEM-8h memory bridge recall (exported for C)."""
    return _bridge_topic_keywords(text)


def looks_like_memory_bridge_cue(text: str) -> bool:
    """Cross-session kw bridge 候補（C で実際に recall する）。"""
    from interaction_orchestrator_mcp.memory_bridge import extract_bridge_keywords
    from interaction_orchestrator_mcp.recall_query import is_temporal_question

    line = (text or "").strip()
    if len(line) < 4:
        return False
    if should_skip_compose_recall(line):
        return False
    if looks_like_stock_calendar_schedule_query(line):
        return False
    if looks_like_future_commitment_cue(line):
        return False
    # Entity/schedule temporal (ねっとわん いつ) → compose 8b / stage-2, not bridge.
    if is_temporal_question(line) and not _HISTORY_Q.search(line):
        return False
    if extract_bridge_keywords(line):
        return True
    return bool(_HISTORY_Q.search(line))


def classify_memory_retrieve_route(
    user_text: str | None,
    *,
    is_recall_utterance: bool = False,
) -> MemoryRetrieveRoute:
    """Decide which memory-retrieve path owns this utterance (Stage-1 gate)."""
    text = (user_text or "").strip()
    if len(text) < 2:
        return "chitchat"

    if is_recall_utterance:
        return "recall_utterance"

    if should_skip_compose_recall(text):
        return "chitchat"

    if looks_like_stock_calendar_schedule_query(text):
        return "calendar_read"

    if looks_like_future_commitment_cue(text):
        return "future_commitment"

    if looks_like_memory_bridge_cue(text):
        return "memory_bridge"

    return "compose_default"


def allows_memory_bridge(route: MemoryRetrieveRoute) -> bool:
    return route == "memory_bridge"


def allows_compose_recall_stage2(route: MemoryRetrieveRoute) -> bool:
    """Stage-2 deep recall — not for calendar stock or OL commitment cues."""
    return route not in {"chitchat", "calendar_read", "future_commitment"}
