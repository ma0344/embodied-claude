"""OL-STALE — stale_policy for open loops (day-crossing close exemptions)."""

from __future__ import annotations

import json
from datetime import date

from social_core.date_resolution import is_resolved_date_stale

STALE_POLICY_DEFAULT = "default"
STALE_POLICY_UNTIL_COMPLETED = "until_completed"
STALE_POLICY_UNTIL_DATE = "until_date"

_UNTIL_COMPLETED_CUES = (
    "終わるまで",
    "日跨",
    "来週まで",
    "来週中",
    "そのうち",
    "忘れないで",
    "覚えておいて",
    "ずっと",
)


def stale_policy_from_detail(detail: dict[str, object]) -> str:
    raw = str(detail.get("stale_policy") or STALE_POLICY_DEFAULT).strip()
    if raw in {STALE_POLICY_UNTIL_COMPLETED, STALE_POLICY_UNTIL_DATE}:
        return raw
    return STALE_POLICY_DEFAULT


def infer_stale_policy_for_loop(
    *,
    utterance: str,
    loop_topic: str,
    resolved_date: date | None,
    needs_date_confirmation: bool,
    temporal_phrase: str | None = None,
) -> tuple[str, str | None]:
    """Return ``(stale_policy, stale_after_iso)`` for a newly created open loop."""
    hay = " ".join(
        part
        for part in (utterance, loop_topic, temporal_phrase or "")
        if part and str(part).strip()
    )
    if any(cue in hay for cue in _UNTIL_COMPLETED_CUES):
        return STALE_POLICY_UNTIL_COMPLETED, None
    if resolved_date is not None:
        return STALE_POLICY_DEFAULT, None
    if needs_date_confirmation:
        return STALE_POLICY_DEFAULT, None
    return STALE_POLICY_UNTIL_COMPLETED, None


def evaluate_stale_close(
    detail_json: str | None,
    *,
    as_of: date,
    include_today: bool = False,
) -> date | None:
    """If this loop should day-stale close, return the resolved/pass date; else None."""
    if not detail_json:
        return None
    try:
        detail: dict[str, object] = json.loads(detail_json)
    except json.JSONDecodeError:
        return None

    policy = stale_policy_from_detail(detail)
    if policy == STALE_POLICY_UNTIL_COMPLETED:
        return None

    if policy == STALE_POLICY_UNTIL_DATE:
        raw = detail.get("stale_after")
        if not raw:
            return None
        try:
            until = date.fromisoformat(str(raw))
        except ValueError:
            return None
        if is_resolved_date_stale(until, as_of=as_of, include_today=include_today):
            return until
        return None

    raw = detail.get("resolved_date")
    if not raw:
        return None
    try:
        resolved = date.fromisoformat(str(raw))
    except ValueError:
        return None
    if is_resolved_date_stale(resolved, as_of=as_of, include_today=include_today):
        return resolved
    return None
