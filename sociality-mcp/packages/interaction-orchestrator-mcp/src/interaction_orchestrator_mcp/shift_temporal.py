"""Temporal filtering for interpretation_shift inject (TEMP-2 / TEMP-4)."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date

from social_core.date_resolution import (
    as_of_date,
    is_resolved_date_stale,
    relativize_for_as_of,
    resolve_relative_date,
)

from .schemas import InterpretationShiftSummary, PrimaryMove

_EXPLICIT_JP_DATE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")


def parse_first_jp_date(text: str) -> date | None:
    """First concrete ``YYYY年M月D日`` in anchored shift text."""
    match = _EXPLICIT_JP_DATE.search(text or "")
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def effective_shift_resolved_date(
    shift: InterpretationShiftSummary,
    *,
    tz_name: str,
) -> date | None:
    """Calendar day the shift's schedule refers to, if any."""
    if shift.resolved_date:
        try:
            return date.fromisoformat(shift.resolved_date)
        except ValueError:
            pass
    parsed = parse_first_jp_date(shift.new_interpretation)
    if parsed is not None:
        return parsed
    return resolve_relative_date(
        topic=shift.new_interpretation,
        updated_at=shift.ts,
        tz_name=tz_name,
    )


def is_shift_temporally_stale(
    shift: InterpretationShiftSummary,
    *,
    as_of_ts: str,
    tz_name: str,
) -> bool:
    """True when shift encodes a schedule day strictly before *as_of*."""
    resolved = effective_shift_resolved_date(shift, tz_name=tz_name)
    if resolved is None:
        return False
    as_of = as_of_date(as_of_ts=as_of_ts, tz_name=tz_name)
    return is_resolved_date_stale(resolved, as_of=as_of)


def filter_injectable_shifts(
    shifts: list[InterpretationShiftSummary],
    *,
    as_of_ts: str,
    tz_name: str,
    limit: int = 3,
) -> list[InterpretationShiftSummary]:
    """Drop stale schedule shifts before compose / plan inject."""
    active = [
        shift
        for shift in shifts
        if not is_shift_temporally_stale(shift, as_of_ts=as_of_ts, tz_name=tz_name)
    ]
    return active[: max(1, min(limit, 10))]


def relativize_shift_for_inject(
    shift: InterpretationShiftSummary,
    *,
    as_of_ts: str,
    tz_name: str,
) -> InterpretationShiftSummary:
    """TEMP-3 — surface anchored dates as 今日/明日 relative to compose *as_of*."""
    as_of = as_of_date(as_of_ts=as_of_ts, tz_name=tz_name)
    return shift.model_copy(
        update={
            "old_interpretation": relativize_for_as_of(shift.old_interpretation, as_of=as_of),
            "new_interpretation": relativize_for_as_of(shift.new_interpretation, as_of=as_of),
        }
    )


def prepare_shifts_for_inject(
    shifts: list[InterpretationShiftSummary],
    *,
    as_of_ts: str,
    tz_name: str,
    limit: int = 3,
) -> list[InterpretationShiftSummary]:
    """Filter stale shifts, then relativize concrete dates for prompt inject."""
    active = filter_injectable_shifts(
        shifts, as_of_ts=as_of_ts, tz_name=tz_name, limit=limit
    )
    return [
        relativize_shift_for_inject(shift, as_of_ts=as_of_ts, tz_name=tz_name)
        for shift in active
    ]


def is_schedule_like_shift(
    shift: InterpretationShiftSummary,
    *,
    tz_name: str,
) -> bool:
    """True when shift text anchors to a calendar day (schedule / plan content)."""
    return effective_shift_resolved_date(shift, tz_name=tz_name) is not None


def append_shift_plan_constraints(
    *,
    must_include: list[str],
    must_avoid: list[str],
    shifts: list[InterpretationShiftSummary],
    user_text: str,
    primary_move: PrimaryMove,
    tz_name: str,
    is_bare_greeting: Callable[[str], bool],
    is_temporal_question: Callable[[str], bool],
    temporal_schedule_contract_enabled: Callable[[], bool],
) -> None:
    """TEMP-4 — compact shift guard; schedule body only on temporal questions."""
    if not shifts or primary_move == "stay_silent":
        return

    latest = shifts[0]
    user = (user_text or "").strip()

    if is_bare_greeting(user):
        must_include.append(
            "bare greeting only — reply briefly (おはよう); do NOT recite schedule "
            "from dream_digest, overnight_inner_voice, or yesterday's episodes; "
            "do NOT volunteer today's plan unless まー asks; hold interpretation "
            "shift in background without regurgitating"
        )
        must_avoid.append(
            "dumping 入浴介助/角煮/予定 from overnight context on a bare おはよう"
        )
        return

    topic_label = latest.topic[:60]
    must_include.append(
        "interpretation shift on "
        f"'{topic_label}': do not regress to the prior interpretation; "
        "details are in [interpretation_shifts] — surface only if まー asks "
        "or the topic is directly on-thread"
    )

    if is_schedule_like_shift(latest, tz_name=tz_name):
        must_avoid.append(
            "volunteering today's schedule from interpretation_shifts unless "
            "まー asks about plans or timing"
        )
        if (
            user
            and is_temporal_question(user)
            and temporal_schedule_contract_enabled()
            and primary_move in {"answer_directly", "answer_with_empathy"}
        ):
            snippet = latest.new_interpretation.strip()[:180]
            if snippet:
                must_include.append(
                    "temporal schedule question — if open loops and memories lack "
                    "a clearer answer, you may state the active interpretation_shift "
                    f"schedule: {snippet}"
                )
