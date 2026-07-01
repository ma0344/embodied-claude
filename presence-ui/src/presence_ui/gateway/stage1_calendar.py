"""GAPI-2r / GAPI-2w — Stage1 calendar_read / calendar_write normalization."""

from __future__ import annotations

import re
from dataclasses import replace

from presence_ui.gateway.calendar_prefetch import looks_like_calendar_query
from presence_ui.gateway.ol_gate import OlGateParsed

_WRITE_CUE_RE = re.compile(
    r"(?:入れて|入れと|登録|追加|ずらし|変更|リスケ|移して|ブロック|延ばし|短く)",
    re.I,
)

CALENDAR_STAGE1_KINDS = frozenset(
    {
        "calendar_read",
        "calendar_write",
        "calendar_operation",  # legacy model output — normalized away
    }
)


def _looks_like_calendar_write_request(text: str) -> bool:
    line = (text or "").strip()
    if not line:
        return False
    return bool(_WRITE_CUE_RE.search(line))


def resolve_calendar_stage1_kind(*, kind: str, utterance: str) -> str:
    """Normalize legacy calendar_operation and reconcile model mistakes."""
    if kind not in CALENDAR_STAGE1_KINDS:
        return kind
    text = (utterance or "").strip()
    if kind == "calendar_read":
        return "calendar_read"
    if kind == "calendar_write":
        return "calendar_write"
    if _looks_like_calendar_write_request(text):
        return "calendar_write"
    if looks_like_calendar_query(text):
        return "calendar_read"
    return "calendar_write"


def normalize_calendar_stage1(stage1: OlGateParsed, *, utterance: str) -> OlGateParsed:
    kind = resolve_calendar_stage1_kind(
        kind=stage1.utterance_kind,
        utterance=utterance,
    )
    if kind == stage1.utterance_kind:
        return stage1
    return replace(stage1, utterance_kind=kind)


def normalized_calendar_kind(*, kind: str | None, utterance: str) -> str | None:
    """Apply normalization to a raw Stage1 kind string."""
    if not kind:
        return None
    return resolve_calendar_stage1_kind(kind=kind, utterance=utterance)
