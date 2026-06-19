"""Deterministic relationship summary helpers."""

from __future__ import annotations

from social_core import clamp01

STRESS_KEYWORDS = ("疲れ", "tired", "stress", "しんど", "overwhelmed", "会議多")
WARMTH_KEYWORDS = ("ありがとう", "thanks", "助か", "嬉し", "good to see")
FUTURE_MARKERS = (
    "明日",
    "tomorrow",
    "later",
    "after",
    "remind",
    "dentist",
    "review",
    "会議",
    "meeting",
    "覚えと",
    "覚えてお",
    "忘れん",
    "忘れない",
    "来週中",
    "今週中",
    "来月中",
)

RECALL_MARKERS = (
    "覚えてる",
    "覚えてます",
    "覚えとる",
    "思い出",
    "remember?",
    "do you remember",
    "recall",
)

FUTURE_REMEMBER_MARKERS = (
    "覚えと",
    "覚えてお",
    "覚えといて",
    "忘れん",
    "忘れない",
    "remind",
    "リマインド",
)

DISMISS_MARKERS = (
    "忘れて",
    "忘れと",
    "忘れる",
    "忘れろ",
    "forget",
    "中止",
    "キャンセル",
    "cancelled",
    "canceled",
    "cancel",
    "やめ",
    "なくなった",
    "しなくていい",
    "もういい",
    "drop it",
    "置いと",
    "置いとい",
    "いらない",
    "不要",
    "もうない",
    "なくなった",
)


def is_recall_utterance(text: str) -> bool:
    """Past-memory questions — not future open loops ('煎餅覚えてる？')."""
    stripped = (text or "").strip()
    if not stripped:
        return False
    if any(marker in stripped for marker in FUTURE_REMEMBER_MARKERS):
        return False
    lowered = stripped.lower()
    return any(marker in stripped or marker in lowered for marker in RECALL_MARKERS)


def is_recall_loop_topic(topic: str) -> bool:
    """Open-loop topics that are recall noise, not actionable follow-ups."""
    compact = (topic or "").strip()
    if not compact:
        return True
    if any(marker in compact for marker in FUTURE_REMEMBER_MARKERS):
        return False
    return any(marker in compact for marker in ("覚えてる", "覚えてます", "覚えとる"))


def is_dismiss_utterance(text: str) -> bool:
    """True when the human asks to drop / cancel / forget a pending thread."""
    lowered = (text or "").lower()
    if not lowered.strip():
        return False
    return any(marker in lowered or marker in text for marker in DISMISS_MARKERS)


def extract_dismiss_topic(text: str) -> str | None:
    """Best-effort topic key for closing an open loop from a dismiss utterance."""
    lowered = (text or "").lower()
    if "dentist" in lowered or "歯医者" in text:
        return "dentist"
    if "pr" in lowered and ("review" in lowered or "レビュー" in text):
        return "pr review"
    if "会議" in text or "meeting" in lowered:
        return "meeting"
    compact = " ".join(lowered.split())
    for marker in DISMISS_MARKERS:
        compact = compact.replace(marker.lower(), " ")
    compact = compact.strip("。.!?？ ,、")
    if 3 <= len(compact) <= 48:
        return compact[:48]
    return None


def compute_snapshot_metrics(
    *,
    interaction_count: int,
    human_messages: list[str],
    agent_messages: list[str],
) -> dict[str, float]:
    """Compute bounded heuristic relationship metrics."""

    stress_hits = sum(
        1 for text in human_messages if any(keyword in text.lower() for keyword in STRESS_KEYWORDS)
    )
    warmth_hits = sum(
        1
        for text in human_messages + agent_messages
        if any(keyword in text.lower() for keyword in WARMTH_KEYWORDS)
    )
    reciprocity = 0.5
    total = len(human_messages) + len(agent_messages)
    if total:
        reciprocity = clamp01(0.5 + (len(human_messages) - len(agent_messages)) / (2 * total))
    return {
        "warmth": clamp01(0.35 + warmth_hits * 0.15),
        "trust": clamp01(0.4 + min(interaction_count, 12) * 0.04),
        "fragility": clamp01(0.15 + stress_hits * 0.18),
        "expected_response_latency": clamp01(0.25 + stress_hits * 0.12),
        "recent_stress": clamp01(0.2 + stress_hits * 0.22),
        "reciprocity_balance": reciprocity,
    }


def summarize_relationship(*, role: str | None, recent_stress: float, open_loop_count: int) -> str:
    """Build a compact relationship summary."""

    role_text = role or "person"
    continuity = "high continuity expectations" if open_loop_count else "light ongoing continuity"
    stress_text = (
        "recent stress is noticeable" if recent_stress >= 0.5 else "recent stress seems manageable"
    )
    return f"{role_text.title()} relationship with {continuity}; {stress_text}."


def suggest_followup_text(context: str, latest_stress_text: str | None) -> tuple[str, str]:
    """Suggest a contextual follow-up without dumping transcripts."""

    if latest_stress_text:
        topic = latest_stress_text.strip("。.!?？ ")[:18]
        return (
            f"{topic}って言うてたけど、そのあと少しは落ち着いた？",
            "References a same-day stress disclosure without overreaching.",
        )
    if context == "evening_checkin":
        return (
            "今日はだいぶ詰まってそうやったけど、少しは一息つけた？",
            "Uses the active context without inventing details.",
        )
    return (
        "いま気になってること、続きある？",
        "Keeps continuity while staying generic.",
    )
