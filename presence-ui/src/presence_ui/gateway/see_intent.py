"""See-intent detection for gateway vision prefetch (pattern A)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

SeeMode = Literal["current", "window", "look_around", "desk", "dining"]

_LOOK_AROUND = re.compile(
    r"(見渡|見回|見回し|見わた|部屋全体|部屋を見渡|look\s*around|scan\s*(?:the\s*)?room)",
    re.IGNORECASE,
)
_DESK = re.compile(
    r"(まー(?:の)?デスク|マー(?:の)?デスク|ma(?:'?s)?\s*desk|\bdesk\b)",
    re.IGNORECASE,
)
_DINING = re.compile(
    r"(ダイニング|食事(?:する)?場所|dining(?:\s*room)?)",
    re.IGNORECASE,
)
_WINDOW = re.compile(
    r"(外|窓|空|ベランダ|庭|look\s*outside|outside|window|sky|weather|天気)",
    re.IGNORECASE,
)
_SEE = re.compile(
    r"(見て|見える|見え|何が見|どう見|room|see\b|look\b|カメラ|撮|映)",
    re.IGNORECASE,
)
_SEE_CUE = re.compile(
    r"(見て|見える|見え|何が見|どう|様子|状況|see\b|look\b)",
    re.IGNORECASE,
)

SEE_PROGRESS_LABELS: dict[SeeMode, str] = {
    "current": "見てる…",
    "window": "外を見てる…",
    "desk": "まーのデスクを見てる…",
    "dining": "ダイニングを見てる…",
    "look_around": "部屋を見渡してる…",
}

SEE_ACTIVITY_LABELS: dict[SeeMode, str] = {
    "current": "見た",
    "window": "外を見た",
    "desk": "まーのデスクを見た",
    "dining": "ダイニングを見た",
    "look_around": "部屋を見た",
}
_EXCLUDE = re.compile(
    r"(覚え|記憶|memor|recall|前に見|さっき見|昨日|思い出)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class SeeIntent:
    mode: SeeMode
    reason: str


def _location_see_intent(
    text: str,
    pattern: re.Pattern[str],
    mode: SeeMode,
    reason: str,
) -> SeeIntent | None:
    if pattern.search(text) and (_SEE.search(text) or _SEE_CUE.search(text)):
        return SeeIntent(mode=mode, reason=reason)
    return None


def detect_see_intent(user_text: str) -> SeeIntent | None:
    """Return a camera capture mode when the user asks to see / look."""
    text = (user_text or "").strip()
    if len(text) < 2:
        return None
    if _EXCLUDE.search(text) and not _SEE.search(text):
        return None
    if _LOOK_AROUND.search(text):
        return SeeIntent(mode="look_around", reason="user asked to scan the room")
    desk = _location_see_intent(
        text,
        _DESK,
        "desk",
        "user asked about ma's desk",
    )
    if desk:
        return desk
    dining = _location_see_intent(
        text,
        _DINING,
        "dining",
        "user asked about the dining area",
    )
    if dining:
        return dining
    if _WINDOW.search(text) and (_SEE.search(text) or _SEE_CUE.search(text)):
        return SeeIntent(mode="window", reason="user asked about outside / window / sky")
    if _SEE.search(text):
        return SeeIntent(mode="current", reason="user asked what is visible")
    return None
