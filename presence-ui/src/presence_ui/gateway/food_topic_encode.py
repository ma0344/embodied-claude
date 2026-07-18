"""Finite food-topic fact encode — dated meal hints for MEM-8h bridge.

Target surface hint (合意 2026-07-18 まー):
  「まーは直近で〇月〇日に麺類（蕎麦）を食べた記録がある」

Allowlist only. Episode transcripts stay elsewhere; bridge gets this one-line card.
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime
from typing import Iterable
from zoneinfo import ZoneInfo

# Dinner-scale / substantial dishes only (軽食・時間帯ワードは encode しない).
FOOD_TOPIC_TOKENS: tuple[str, ...] = (
    "冷たいラーメン",
    "ざる蕎麦",
    "かけ蕎麦",
    "ラーメン",
    "うどん",
    "そば",
    "蕎麦",
    "麺類",
    "麺",
    "丼",
    "カレー",
)

NOODLE_DISHES: frozenset[str] = frozenset(
    {
        "冷たいラーメン",
        "ざる蕎麦",
        "かけ蕎麦",
        "ラーメン",
        "うどん",
        "そば",
        "蕎麦",
        "麺",
    }
)


def food_topic_encode_enabled() -> bool:
    """Legacy episode_close → LTM meal write. Default off (UserAction meal is canonical)."""
    raw = os.getenv("PRESENCE_FOOD_TOPIC_FACTS", "0").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def foods_mentioned_in_text(text: str) -> list[str]:
    """Return allowlisted food tokens found in text (longest-first, deduped)."""
    remaining = text or ""
    found: list[str] = []
    seen: set[str] = set()
    for token in FOOD_TOPIC_TOKENS:
        if token not in remaining:
            continue
        label = "蕎麦" if token == "そば" else token
        if label not in seen:
            seen.add(label)
            found.append(label)
        remaining = remaining.replace(token, " " * len(token))
    return found


def foods_mentioned_in_turns(
    turns: Iterable[dict[str, str | None]],
    *,
    senders: frozenset[str] = frozenset({"ma"}),
) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for turn in turns:
        sender = str(turn.get("sender") or "").strip().lower()
        if sender not in senders:
            continue
        for food in foods_mentioned_in_text(str(turn.get("message") or "")):
            if food not in seen:
                seen.add(food)
                found.append(food)
    return found


def _parse_to_date(raw: str | date | datetime | None, *, tz_name: str = "Asia/Tokyo") -> date | None:
    if raw is None:
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        dt = raw
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(tz_name))
        return dt.astimezone(ZoneInfo(tz_name)).date()
    text = str(raw).strip()
    if not text:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return date.fromisoformat(text)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(tz_name))
        return dt.astimezone(ZoneInfo(tz_name)).date()
    except ValueError:
        return None


def format_jp_month_day(raw: str | date | datetime | None, *, tz_name: str = "Asia/Tokyo") -> str | None:
    """Format as ``7月1日`` for surface hints."""
    day = _parse_to_date(raw, tz_name=tz_name)
    if day is None:
        return None
    return f"{day.month}月{day.day}日"


def _food_surface_label(food: str) -> str:
    return "蕎麦" if food == "そば" else food


def format_food_topic_fact(
    food: str,
    *,
    on_date: str | date | datetime | None = None,
    tz_name: str = "Asia/Tokyo",
) -> str:
    """One-line meal record hint for bridge / compose.

    Example: ``まーは直近で7月1日に麺類（蕎麦）を食べた記録がある``
    """
    day = format_jp_month_day(on_date, tz_name=tz_name) or "最近"
    label = _food_surface_label(food)
    if label in NOODLE_DISHES:
        return f"まーは直近で{day}に麺類（{label}）を食べた記録がある"
    if label == "麺類":
        return f"まーは直近で{day}に麺類を食べた記録がある"
    return f"まーは直近で{day}に{label}を食べた記録がある"


def format_cook_topic_fact(
    food: str,
    *,
    on_date: str | date | datetime | None = None,
    tz_name: str = "Asia/Tokyo",
) -> str:
    """Cook-only card — does not claim the meal was eaten.

    Example: ``まーは直近で7月1日にカレーを作った記録がある``
    """
    day = format_jp_month_day(on_date, tz_name=tz_name) or "最近"
    label = _food_surface_label(food)
    if label in NOODLE_DISHES:
        return f"まーは直近で{day}に麺類（{label}）を作った記録がある"
    if label == "麺類":
        return f"まーは直近で{day}に麺類を作った記録がある"
    return f"まーは直近で{day}に{label}を作った記録がある"


def food_topic_facts_from_turns(
    turns: Iterable[dict[str, str | None]],
    *,
    tz_name: str = "Asia/Tokyo",
) -> list[str]:
    """Build dated facts from まー turns — date = latest turn that mentioned that food."""
    latest: dict[str, str | None] = {}
    order: list[str] = []
    for turn in turns:
        sender = str(turn.get("sender") or "").strip().lower()
        if sender != "ma":
            continue
        ts = turn.get("timestamp") or turn.get("ts")
        for food in foods_mentioned_in_text(str(turn.get("message") or "")):
            if food not in latest:
                order.append(food)
            latest[food] = str(ts) if ts else latest.get(food)
    return [
        format_food_topic_fact(food, on_date=latest.get(food), tz_name=tz_name)
        for food in order
    ]
