"""Deterministic relationship summary helpers."""

from __future__ import annotations

import re

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

FOLLOW_UP_LOOP_MARKERS = (
    "明日",
    "tomorrow",
    "今日中",
    "来週",
    "今週中",
    "来月中",
    "また",
    "続き",
    "後で",
    "リマインド",
    "remind me",
    "remind ",
    "忘れん",
    "忘れない",
    "会議",
    "meeting",
    "dentist",
    "歯医者",
)

_TRAILING_REMEMBER_TAIL = (
    r"(?:[。．!！]|(?:よ|ね|な|わ|さ|かな|や|で)[。．!！]?)?$"
)

# Keep in sync with ``.claude/hooks/memory_auto_save.py`` (_CONTENT_PATTERNS / _TRIGGER_HINT).
_ARCHIVE_REMEMBER_CONTENT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        rf"^(.+?)(?:を|って)?(?:覚えておいて|覚えといて|覚えとく|記憶して|記憶しといて){_TRAILING_REMEMBER_TAIL}",
        re.DOTALL,
    ),
    re.compile(
        r"^(?:覚えておいて|覚えといて|記憶して|記憶しといて)[：:\s]+(.+)$",
        re.DOTALL,
    ),
    re.compile(
        r"^(?:remember(?:\s+this|\s+forever)?|store\s+this(?:\s+permanently)?)"
        r"[：:\s]+(.+)$",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"^(.+?)\s+(?:please\s+)?remember(?:\s+this|\s+forever)?[.!]?$",
        re.IGNORECASE | re.DOTALL,
    ),
)

_ARCHIVE_IMPERATIVE_ONLY = re.compile(
    rf"^(?:これ|それ|あれ)?(?:を)?(?:覚えておいて|覚えといて|記憶して|記憶しといて){_TRAILING_REMEMBER_TAIL}",
)

_REMEMBER_TRIGGER_HINT = re.compile(
    r"(覚えておいて|覚えといて|覚えとく|記憶して|記憶しといて|"
    r"remember\s+forever|remember\s+this|store\s+this)",
    re.IGNORECASE,
)

_QUOTED_JA = re.compile(r"[「『]([^」』]+)[」』]")
_LEADING_FILLER = re.compile(
    r"^(?:今度は|今回は|次は|次から|もう一度|あらためて|改めて|ちなみに)[、,\s]*",
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


def _normalize_archive_content(raw: str) -> str:
    content = raw.strip()
    quoted = _QUOTED_JA.findall(content)
    if quoted:
        return quoted[-1].strip()
    content = _LEADING_FILLER.sub("", content).strip()
    content = re.sub(r"^[「『\"']+|[」』\"']+$", "", content).strip()
    return content.strip("、, ")


def extract_archive_remember_content(text: str) -> str | None:
    """Extract storable content from an archival remember utterance (MEM-8f)."""
    stripped = (text or "").strip()
    if len(stripped) < 4 or not _REMEMBER_TRIGGER_HINT.search(stripped):
        return None
    if _ARCHIVE_IMPERATIVE_ONLY.match(stripped):
        return None
    for pattern in _ARCHIVE_REMEMBER_CONTENT_PATTERNS:
        match = pattern.match(stripped)
        if not match:
            continue
        content = _normalize_archive_content(match.group(1).strip())
        if len(content) >= 2:
            return content
    return None


def has_follow_up_loop_markers(text: str) -> bool:
    """True when the utterance signals ongoing follow-up, not archive-only."""
    stripped = (text or "").strip()
    if not stripped:
        return False
    lowered = stripped.lower()
    if any(marker in stripped or marker in lowered for marker in FOLLOW_UP_LOOP_MARKERS):
        return True
    if "pr" in lowered and ("review" in lowered or "レビュー" in stripped):
        return True
    return False


def is_archive_remember_utterance(text: str) -> bool:
    """Storage-for-later remember — skip open-loop creation (MEM-8f / OL-ARCHIVE 2)."""
    if is_recall_utterance(text):
        return False
    if has_follow_up_loop_markers(text):
        return False
    return extract_archive_remember_content(text) is not None


def has_remember_save_trigger(text: str) -> bool:
    stripped = (text or "").strip()
    return len(stripped) >= 4 and bool(_REMEMBER_TRIGGER_HINT.search(stripped))


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
