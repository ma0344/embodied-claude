"""MEM-8g — compose topic retire (explicit tokens, no regex filters)."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from social_core import utc_now

if TYPE_CHECKING:
    from social_core import SocialDB

# Finite completion markers — gate only (not open-ended regex).
_COMPLETION_MARKERS: tuple[str, ...] = (
    "もう作った",
    "もう作って",
    "作ったよ",
    "作ったわ",
    "済んだ",
    "済ませた",
    "さっきやった",
    "もうやった",
    "終わった",
    "終えた",
    "もう食べた",
    "食べたよ",
    "もう済み",
)

# Meal-slot phrases — retire only as a whole, never as generic 2-grams.
_MEAL_SLOT_COMPOUNDS: tuple[str, ...] = (
    "お昼ご飯",
    "昼ご飯",
    "朝ご飯",
    "晩ご飯",
    "晩御飯",
    "夜ご飯",
    "昼食",
)

# Named dishes / ingredients — specific enough to retire without blocking other meals.
_SPECIFIC_FOOD_HINTS: tuple[str, ...] = (
    "蕎麦",
    "うどん",
    "ラーメン",
    "お好み焼き",
    "パスタ",
    "カレー",
    "サンドイッチ",
    "オムライス",
    "チャーハン",
    "味噌汁",
)

_LUNCH_SLOTS: frozenset[str] = frozenset({"お昼ご飯", "昼ご飯", "昼食"})
_LUNCH_BAND_HINTS: tuple[str, ...] = ("お昼", "昼ご飯", "お昼ご飯", "昼食", "ランチ")


def _focus_before_completion(text: str) -> str:
    """Utterance span before the completion marker (what was finished)."""
    line = (text or "").strip()
    cut = len(line)
    for marker in _COMPLETION_MARKERS:
        idx = line.find(marker)
        if idx != -1 and idx < cut:
            cut = idx
    return line[:cut].strip() if cut < len(line) else line


def extract_retire_topics(text: str) -> list[str]:
    """Pull **narrow** retire tokens — not broad meal-category bans.

    Example: 「お昼ご飯の蕎麦はもう作ったよ」 → ``お昼ご飯の蕎麦``, ``お昼ご飯``, ``蕎麦``.
    ``お昼ご飯の準備``（蕎麦なし）も slot 一致で compose から落ちる。晩御飯は別帯のまま。
    """
    full = (text or "").strip()
    if not full:
        return []
    focus = _focus_before_completion(full)
    topics: list[str] = []
    seen: set[str] = set()

    def add(token: str) -> None:
        token = token.strip()
        if len(token) < 2 or len(token) > 24 or token in seen:
            return
        seen.add(token)
        topics.append(token)

    foods_in_focus = [food for food in _SPECIFIC_FOOD_HINTS if food in focus]

    slots_in_full = [slot for slot in _MEAL_SLOT_COMPOUNDS if slot in full]
    slots_in_full.sort(key=len, reverse=True)
    distinct_slots: list[str] = []
    for slot in slots_in_full:
        if any(slot in kept or kept in slot for kept in distinct_slots):
            continue
        distinct_slots.append(slot)

    for slot in distinct_slots:
        thread_closed = False
        for food in foods_in_focus:
            thread = f"{slot}の{food}"
            if thread in full:
                add(thread)
                thread_closed = True
        if thread_closed:
            add(slot)
        elif slot in focus and not foods_in_focus:
            add(slot)

    for food in foods_in_focus:
        add(food)

    return topics[:6]


def topic_retire_enabled() -> bool:
    raw = os.getenv("PRESENCE_COMPOSE_TOPIC_RETIRE", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def topic_retire_hours() -> int:
    raw = os.getenv("PRESENCE_TOPIC_RETIRE_HOURS", "36").strip()
    try:
        return max(1, min(int(raw), 168))
    except ValueError:
        return 36


def detect_user_completion_utterance(text: str) -> bool:
    line = (text or "").strip()
    if len(line) < 4:
        return False
    return any(marker in line for marker in _COMPLETION_MARKERS)


def memory_matches_retired_topics(content: str, topics: list[str]) -> bool:
    body = content or ""
    return any(topic in body for topic in topics if topic)


def user_text_reopens_topic(user_text: str, topics: list[str]) -> bool:
    line = user_text or ""
    return any(topic in line for topic in topics if topic)


def _pivot_reopen_topics(user_text: str, active: list[str]) -> list[str]:
    """Re-open a closed lunch thread when まー names a different dish for that band."""
    line = user_text or ""
    retired_foods = {topic for topic in active if topic in _SPECIFIC_FOOD_HINTS}
    if not retired_foods:
        return []
    mentioned_foods = {food for food in _SPECIFIC_FOOD_HINTS if food in line}
    new_foods = mentioned_foods - retired_foods
    if not new_foods:
        return []
    lunch_slots_active = {topic for topic in active if topic in _LUNCH_SLOTS}
    if not lunch_slots_active:
        return []
    if not any(hint in line for hint in _LUNCH_BAND_HINTS):
        return []

    reopen: set[str] = set()
    for topic in active:
        if topic in retired_foods or topic in lunch_slots_active:
            reopen.add(topic)
        for slot in lunch_slots_active:
            for food in retired_foods:
                if topic == f"{slot}の{food}":
                    reopen.add(topic)
    return list(reopen)


@dataclass(frozen=True, slots=True)
class RetiredTopicSet:
    topics: tuple[str, ...]
    retired_until: str


class TopicRetireStore:
    """Persist retired compose topics per person (SQLite)."""

    def __init__(self, db: SocialDB) -> None:
        self.db = db

    def _purge_expired(self, *, person_id: str, now_iso: str) -> None:
        self.db.execute(
            """
            DELETE FROM compose_topic_retire
            WHERE person_id = ? AND retired_until <= ?
            """,
            (person_id, now_iso),
        )

    def active_retired_topics(self, *, person_id: str) -> list[str]:
        if not topic_retire_enabled() or not person_id:
            return []
        now_iso = utc_now()
        self._purge_expired(person_id=person_id, now_iso=now_iso)
        rows = self.db.fetchall(
            """
            SELECT topics_json FROM compose_topic_retire
            WHERE person_id = ? AND retired_until > ?
            ORDER BY created_at DESC
            """,
            (person_id, now_iso),
        )
        merged: list[str] = []
        seen: set[str] = set()
        for row in rows:
            try:
                items = json.loads(str(row["topics_json"] or "[]"))
            except json.JSONDecodeError:
                continue
            if not isinstance(items, list):
                continue
            for item in items:
                token = str(item).strip()
                if len(token) >= 2 and token not in seen:
                    seen.add(token)
                    merged.append(token)
        return merged

    def retire_topics(
        self,
        *,
        person_id: str,
        topics: list[str],
        source_utterance: str = "",
    ) -> None:
        if not topic_retire_enabled() or not person_id:
            return
        cleaned = [t for t in topics if t and len(t) >= 2]
        if not cleaned:
            return
        now = datetime.now(timezone.utc)
        retired_until = (now + timedelta(hours=topic_retire_hours())).isoformat()
        retire_id = f"ret_{uuid.uuid4().hex[:12]}"
        self.db.execute(
            """
            INSERT INTO compose_topic_retire(
                retire_id, person_id, topics_json, retired_until,
                source_utterance, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                retire_id,
                person_id,
                json.dumps(cleaned, ensure_ascii=False),
                retired_until,
                (source_utterance or "")[:500],
                utc_now(),
            ),
        )

    def clear_matching_topics(self, *, person_id: str, user_text: str) -> None:
        """Drop retired tokens that まー explicitly mentions again (re-open)."""
        if not person_id:
            return
        active = self.active_retired_topics(person_id=person_id)
        line = user_text or ""
        reopen = [topic for topic in active if topic in line]
        reopen.extend(_pivot_reopen_topics(line, active))
        reopen = list(dict.fromkeys(reopen))
        if not reopen:
            return
        now_iso = utc_now()
        rows = self.db.fetchall(
            """
            SELECT retire_id, topics_json FROM compose_topic_retire
            WHERE person_id = ? AND retired_until > ?
            """,
            (person_id, now_iso),
        )
        for row in rows:
            try:
                items = [str(x).strip() for x in json.loads(str(row["topics_json"] or "[]"))]
            except json.JSONDecodeError:
                continue
            kept = [item for item in items if item not in reopen]
            if kept == items:
                continue
            if not kept:
                self.db.execute(
                    "DELETE FROM compose_topic_retire WHERE retire_id = ?",
                    (str(row["retire_id"]),),
                )
            else:
                self.db.execute(
                    """
                    UPDATE compose_topic_retire
                    SET topics_json = ?
                    WHERE retire_id = ?
                    """,
                    (json.dumps(kept, ensure_ascii=False), str(row["retire_id"])),
                )


def maybe_record_topic_retire(
    db: SocialDB | None,
    *,
    person_id: str | None,
    user_text: str | None,
) -> bool:
    """On completion-shaped まー utterance, retire extracted topics for compose."""
    if db is None or not person_id:
        return False
    text = (user_text or "").strip()
    if not detect_user_completion_utterance(text):
        return False
    store = TopicRetireStore(db)
    store.clear_matching_topics(person_id=person_id, user_text=text)
    topics = extract_retire_topics(text)
    if not topics:
        return False
    store.retire_topics(person_id=person_id, topics=topics, source_utterance=text)
    return True
