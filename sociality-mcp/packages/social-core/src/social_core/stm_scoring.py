"""MEM-5 v1 — score STM rows for Dreaming promotion (prototype).

Scores **STM entries**, not raw chat JSONL. Salience metadata (`metadata_json`)
will replace heuristics once wired at append time.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from social_core.stm import StmEntry

EMOTION_WEIGHTS: dict[str, float] = {
    "moved": 0.9,
    "excited": 0.85,
    "nostalgic": 0.75,
    "sad": 0.75,
    "curious": 0.65,
    "happy": 0.6,
    "surprised": 0.6,
    "neutral": 0.35,
}

TOPIC_PATTERNS: dict[str, tuple[str, ...]] = {
    "residence": ("松本", "長野", "住んで", "家は"),
    "weather": ("天気", "晴れ", "雨", "曇り", "予報"),
    "home_helper": ("ヘルパー", "入浴介助", "入浴"),
    "greeting": ("おはよう", "おかえり", "こんばんは"),
    "camera": ("カメラ", "見て", "見え"),
    "fatigue_care": ("疲れ", "お疲れ", "ゆっくり"),
    "commitment": ("約束", "言ってた", "リマインド", "忘れない"),
}

PROMOTE_THRESHOLD = 0.55
PROMOTE_STRONG_THRESHOLD = 0.72

BYPASS_KINDS = frozenset(
    {"interpretation_shift", "agent_boundary", "remember_direct"}
)
SKIP_KINDS = frozenset({"wm_turn_ma", "wm_turn_koyori"})


@dataclass(slots=True)
class StmScoreBreakdown:
    entry_id: str
    kind: str
    source: str
    local_day: str
    topics: list[str] = field(default_factory=list)
    inferred_emotion: str = "neutral"
    emotion_score: float = 0.0
    interest_score: float = 0.0
    frequency_score: float = 0.0
    recency_score: float = 0.0
    promote_score: float = 0.0
    decision: str = "hold"
    reason: str = ""
    summary_preview: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "kind": self.kind,
            "source": self.source,
            "local_day": self.local_day,
            "topics": self.topics,
            "inferred_emotion": self.inferred_emotion,
            "emotion_score": round(self.emotion_score, 3),
            "interest_score": round(self.interest_score, 3),
            "frequency_score": round(self.frequency_score, 3),
            "recency_score": round(self.recency_score, 3),
            "promote_score": round(self.promote_score, 3),
            "decision": self.decision,
            "reason": self.reason,
            "summary_preview": self.summary_preview,
        }


def detect_topics(summary: str) -> list[str]:
    text = summary or ""
    found = [name for name, patterns in TOPIC_PATTERNS.items() if any(p in text for p in patterns)]
    return found


def _infer_emotion(entry: StmEntry, topics: list[str]) -> str:
    text = entry.summary or ""
    if entry.kind in {"interpretation_shift", "agent_boundary"}:
        return "moved"
    if any(t in topics for t in ("residence", "home_helper", "fatigue_care")):
        return "moved"
    if "weather" in topics and entry.source == "episode_summary":
        return "curious"
    if entry.kind == "agent_private_reflection":
        return "neutral"
    if re.search(r"ありがとう|優しさ|教えてくれた", text):
        return "moved"
    if "greeting" in topics and len(topics) == 1:
        return "neutral"
    return "curious" if "weather" in topics else "neutral"


def _emotion_score(entry: StmEntry, emotion_tag: str) -> float:
    table = EMOTION_WEIGHTS.get(emotion_tag, 0.35)
    importance_norm = max(1, min(entry.importance, 5)) / 5.0
    return 0.6 * table + 0.4 * importance_norm


def _interest_score(entry: StmEntry, topics: list[str], metadata: dict[str, Any]) -> float:
    desire_level = float(metadata.get("desire_level") or 0.0)
    if metadata.get("explicit_remember"):
        return 1.0
    if entry.kind in BYPASS_KINDS:
        return 0.95
    if entry.source == "episode_summary":
        base = 0.75
        if "residence" in topics or "home_helper" in topics:
            base = 0.9
        elif "commitment" in topics:
            base = 0.85
        elif "greeting" in topics and len(topics) <= 2:
            base = 0.45
        return max(base, desire_level)
    if entry.kind == "open_loop_progress":
        if "home_helper" in topics or "residence" in topics:
            return 0.8
        if "weather" in topics:
            return 0.55
        return 0.5
    if entry.kind == "agent_private_reflection":
        return 0.4
    return max(0.35, desire_level)


def _frequency_score(entry: StmEntry, topics: list[str], day_entries: list[StmEntry]) -> float:
    if not topics:
        return 0.2
    topic_set = set(topics)
    matches = 0
    for other in day_entries:
        if other.entry_id == entry.entry_id:
            continue
        other_topics = set(detect_topics(other.summary))
        if topic_set & other_topics:
            matches += 1
    return min(1.0, matches / 3.0)


def _recency_score(entry: StmEntry, *, now: datetime | None = None) -> float:
    try:
        ts = datetime.fromisoformat(entry.ts.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=datetime.now().astimezone().tzinfo)
        ref = now or datetime.now(ts.tzinfo)
        hours = max(0.0, (ref - ts).total_seconds() / 3600.0)
        if hours <= 6:
            return 1.0
        if hours <= 24:
            return 0.85
        if hours <= 72:
            return 0.6
        return 0.35
    except ValueError:
        return 0.7


def _parse_metadata(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def score_stm_entry(
    entry: StmEntry,
    *,
    day_entries: list[StmEntry] | None = None,
    metadata_json: str | None = None,
    now: datetime | None = None,
) -> StmScoreBreakdown:
    """Return promotion score + decision for one STM row."""
    if entry.kind in SKIP_KINDS:
        return StmScoreBreakdown(
            entry_id=entry.entry_id,
            kind=entry.kind,
            source=entry.source,
            local_day=entry.local_day,
            decision="skip",
            reason="wm_turn noise",
            summary_preview=(entry.summary or "")[:80],
        )

    metadata = _parse_metadata(metadata_json)
    topics = detect_topics(entry.summary)
    emotion_tag = str(metadata.get("emotion_tag") or _infer_emotion(entry, topics))
    emotion = _emotion_score(entry, emotion_tag)
    interest = _interest_score(entry, topics, metadata)
    frequency = _frequency_score(entry, topics, day_entries or [entry])
    recency = _recency_score(entry, now=now)

    promote_score = (
        0.25 * recency + 0.20 * frequency + 0.30 * emotion + 0.25 * interest
    )

    decision = "hold"
    reason = ""

    session_id = entry.session_id or ""
    if session_id.startswith("smoke_"):
        decision = "skip"
        reason = "smoke test session"
    elif entry.kind in BYPASS_KINDS or metadata.get("explicit_remember"):
        decision = "promote"
        reason = "explicit / bypass kind"
    elif entry.importance >= 5:
        decision = "promote"
        reason = "importance=5"
    elif (
        entry.source == "episode_summary"
        and "residence" in topics
        and len((entry.summary or "").strip()) > 40
    ):
        decision = "promote"
        reason = "episode + residence fact"
    elif entry.source == "episode_summary" and "commitment" in topics:
        decision = "promote"
        reason = "episode + commitment"
    elif entry.kind == "open_loop_progress" and frequency > 0:
        newest_id = _newest_matching(day_entries or [], topics, entry.entry_id)
        if entry.entry_id != newest_id:
            decision = "merge"
            reason = "duplicate topic — keep newest only"
        elif promote_score >= PROMOTE_THRESHOLD:
            decision = "promote"
            reason = "high frequency topic"
        else:
            decision = "hold"
            reason = "frequency without salience"
    elif entry.kind == "agent_private_reflection":
        decision = "hold"
        reason = "private reflection — daybook only"
    elif promote_score >= PROMOTE_STRONG_THRESHOLD:
        decision = "promote"
        reason = f"score>={PROMOTE_STRONG_THRESHOLD}"
    elif promote_score >= PROMOTE_THRESHOLD:
        decision = "promote"
        reason = f"score>={PROMOTE_THRESHOLD}"
    elif entry.source == "episode_summary" and "greeting" in topics and len(topics) <= 2:
        decision = "hold"
        reason = "greeting-only episode"
    else:
        decision = "hold"
        reason = "below threshold"

    return StmScoreBreakdown(
        entry_id=entry.entry_id,
        kind=entry.kind,
        source=entry.source,
        local_day=entry.local_day,
        topics=topics,
        inferred_emotion=emotion_tag,
        emotion_score=emotion,
        interest_score=interest,
        frequency_score=frequency,
        recency_score=recency,
        promote_score=promote_score,
        decision=decision,
        reason=reason,
        summary_preview=(entry.summary or "").replace("\n", " ")[:100],
    )


def _newest_matching(entries: list[StmEntry], topics: list[str], entry_id: str) -> str:
    topic_set = set(topics)
    matching = [
        e
        for e in entries
        if topic_set & set(detect_topics(e.summary))
    ]
    if not matching:
        return entry_id
    matching.sort(key=lambda e: e.ts, reverse=True)
    return matching[0].entry_id


def score_stm_batch(
    entries: list[StmEntry],
    *,
    metadata_by_id: dict[str, str] | None = None,
) -> list[StmScoreBreakdown]:
    by_day: dict[str, list[StmEntry]] = {}
    for entry in entries:
        by_day.setdefault(entry.local_day, []).append(entry)
    meta = metadata_by_id or {}
    results: list[StmScoreBreakdown] = []
    for entry in entries:
        results.append(
            score_stm_entry(
                entry,
                day_entries=by_day.get(entry.local_day, []),
                metadata_json=meta.get(entry.entry_id),
            )
        )
    return results
