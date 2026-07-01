"""GAPI-2r-S2 — unified calendar read pipeline (chat + ingest)."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from presence_ui.gapi.auth import GoogleAuthError, get_calendar_service
from presence_ui.gapi.calendar_client import list_events_in_time_range
from presence_ui.gapi.policy import load_google_policy
from presence_ui.gateway.calendar_prefetch import (
    calendar_prefetch_enabled,
    format_calendar_prefetch_with_directive,
    looks_like_calendar_query,
)
from presence_ui.gateway.calendar_read_window import resolve_prefetch_window
from presence_ui.gateway.stage1_calendar import normalized_calendar_kind

logger = logging.getLogger(__name__)


def calendar_read_staged_enabled() -> bool:
    """Stage1 calendar_read gate for chat prefetch (GAPI-2r-S2)."""
    if not calendar_prefetch_enabled():
        return False
    raw = os.getenv("PRESENCE_GAPI_CALENDAR_READ_STAGED", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def classify_calendar_read_stage1(*, utterance: str) -> str | None:
    """Run TEMP-C Stage1 only; return normalized utterance_kind (or None if classifier down)."""
    from presence_ui.gateway.temp_c_staged import run_stage1_classify

    stage1 = run_stage1_classify(utterance=utterance)
    if stage1 is None:
        return None
    return stage1.utterance_kind


def should_run_calendar_read(text: str) -> bool:
    """True when gateway should list calendar events for this utterance."""
    if not calendar_prefetch_enabled():
        return False
    line = (text or "").strip()
    if not line:
        return False
    if not looks_like_calendar_query(line):
        return False
    if not calendar_read_staged_enabled():
        return True
    kind = classify_calendar_read_stage1(utterance=line)
    if kind is None:
        logger.warning(
            "GAPI-2r-S2: Stage1 unavailable for calendar cue %r — skipping read",
            line[:80],
        )
        return False
    return normalized_calendar_kind(kind=kind, utterance=line) == "calendar_read"


def run_calendar_read_pipeline(
    utterance: str,
    *,
    anchor_iso: str | None = None,
) -> tuple[str, str]:
    """Resolve window (C4 → e4b) · list events · return prefetch block + status."""
    from presence_ui.gateway.calendar_prefetch import _format_error_block

    policy = load_google_policy()
    if not policy.enabled:
        return (
            _format_error_block(
                policy=policy,
                status="disabled",
                detail="gapi-policy google.enabled is false or policy missing",
            ),
            "disabled",
        )
    if not policy.readable_calendars():
        return (
            _format_error_block(
                policy=policy,
                status="disabled",
                detail="no readable calendars in gapi-policy",
            ),
            "disabled",
        )

    tz = ZoneInfo(policy.timezone)
    if anchor_iso is None:
        anchor_iso = datetime.now(tz).isoformat(timespec="seconds")

    window = resolve_prefetch_window(
        utterance,
        anchor_iso=anchor_iso,
        tz_name=policy.timezone,
        fallback_day_range=policy.prefetch_day_range,
    )

    if window.resolution == "ambiguous":
        block = format_calendar_prefetch_with_directive(
            policy=policy,
            events=[],
            status="ambiguous",
            window=window,
        )
        return block, "ambiguous"

    try:
        service = get_calendar_service()
        events = list_events_in_time_range(
            service,
            policy,
            time_min=window.start,
            time_max=window.end,
            search_query=window.search_query,
        )
    except GoogleAuthError as exc:
        return (
            _format_error_block(
                policy=policy,
                status="error",
                detail=str(exc),
                range_label=window.range_label,
            ),
            "error",
        )
    except Exception as exc:  # noqa: BLE001
        return (
            _format_error_block(
                policy=policy,
                status="error",
                detail=str(exc),
                range_label=window.range_label,
            ),
            "error",
        )

    status = "ok" if events else "empty"
    block = format_calendar_prefetch_with_directive(
        policy=policy,
        events=events,
        status=status,
        window=window,
    )
    return block, status


def process_calendar_read_staged_ingest(
    *,
    person_id: str,
    utterance: str,
    ts: str,
) -> tuple[str, str] | None:
    """Ingest path — same pipeline as chat (no compose inject here)."""
    text = (utterance or "").strip()
    if not text:
        return None
    block, status = run_calendar_read_pipeline(text, anchor_iso=ts)
    logger.info(
        "GAPI-2r-S2 calendar_read ingest person=%s status=%s chars=%d",
        person_id,
        status,
        len(block),
    )
    return block, status
