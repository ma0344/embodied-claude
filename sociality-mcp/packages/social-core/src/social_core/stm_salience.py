"""MEM-5b — salience snapshot for STM metadata_json at append time."""

from __future__ import annotations

import json
import re
from types import SimpleNamespace
from typing import Any

from social_core.stm_scoring import _infer_emotion, detect_topics

VALID_EMOTIONS = frozenset(
    {
        "happy",
        "sad",
        "surprised",
        "moved",
        "excited",
        "nostalgic",
        "curious",
        "neutral",
    }
)


def _dominant_from_desires_json(raw: str | None) -> tuple[str | None, float]:
    if not raw:
        return None, 0.0
    try:
        desires = json.loads(raw)
    except json.JSONDecodeError:
        return None, 0.0
    if not isinstance(desires, dict) or not desires:
        return None, 0.0
    best_name: str | None = None
    best_level = 0.0
    for name, level in desires.items():
        try:
            value = float(level)
        except (TypeError, ValueError):
            continue
        if value > best_level:
            best_level = value
            best_name = str(name)
    return best_name, best_level


def match_open_loop_ids(
    summary: str,
    loops: list[tuple[str, str]],
    *,
    min_topic_len: int = 2,
) -> list[str]:
    """Return open_loop loop_ids whose topic overlaps the summary text."""
    text = summary or ""
    matched: list[str] = []
    seen: set[str] = set()
    for loop_id, topic in loops:
        topic = (topic or "").strip()
        if len(topic) < min_topic_len or loop_id in seen:
            continue
        if topic in text:
            matched.append(loop_id)
            seen.add(loop_id)
            continue
        split_pattern = r"[\s、。．，,.!?！？の]+"
        fragments = [w for w in re.split(split_pattern, topic) if len(w) >= min_topic_len]
        if len(topic) >= min_topic_len:
            for index in range(len(topic) - min_topic_len + 1):
                piece = topic[index : index + min_topic_len]
                if piece not in fragments:
                    fragments.append(piece)
        if any(fragment in text for fragment in fragments):
            matched.append(loop_id)
            seen.add(loop_id)
    return matched


def build_stm_salience_metadata(
    *,
    summary: str,
    kind: str,
    source: str,
    importance: int,
    dominant_desire: str | None = None,
    desire_level: float | None = None,
    open_loop_ids: list[str] | None = None,
    explicit_remember: bool = False,
    emotion_tag: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build metadata_json payload for one STM row."""
    topics = detect_topics(summary)
    probe = SimpleNamespace(summary=summary, kind=kind, source=source)
    tag = emotion_tag or _infer_emotion(probe, topics)  # type: ignore[arg-type]
    if tag not in VALID_EMOTIONS:
        tag = "neutral"

    meta: dict[str, Any] = {
        "emotion_tag": tag,
        "importance": max(1, min(importance, 5)),
        "topics": topics,
    }
    if dominant_desire:
        meta["dominant_desire"] = dominant_desire
    if desire_level is not None and desire_level > 0:
        meta["desire_level"] = round(desire_level, 3)
    if open_loop_ids:
        meta["open_loop_ids"] = open_loop_ids
    if explicit_remember:
        meta["explicit_remember"] = True
    if extra:
        meta.update(extra)
    return meta


def salience_from_experience_row(
    row: Any,
    *,
    open_loops: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Build salience from an agent_experiences DB row."""
    summary = str(row["summary"])
    kind = str(row["kind"])
    importance = int(row["importance"])
    dominant, level = _dominant_from_desires_json(row["desires_after_json"])
    if dominant is None:
        dominant, level = _dominant_from_desires_json(row["desires_before_json"])
    loop_ids = match_open_loop_ids(summary, open_loops or [])
    explicit = kind in {"remember_direct", "interpretation_shift"}
    return build_stm_salience_metadata(
        summary=summary,
        kind=kind,
        source="experience_mirror",
        importance=importance,
        dominant_desire=dominant,
        desire_level=level or None,
        open_loop_ids=loop_ids or None,
        explicit_remember=explicit,
    )
