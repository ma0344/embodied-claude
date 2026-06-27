"""Tests for GAPI calendar write helpers (no network)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from presence_ui.gapi.calendar_writes import (
    CalendarWriteError,
    calendar_by_id,
    default_smoke_slot,
    require_create_allowed,
    require_update_allowed,
    run_write_smoke,
)
from presence_ui.gapi.policy import CalendarPolicy, GooglePolicy


def _writable_policy() -> GooglePolicy:
    return GooglePolicy(
        enabled=True,
        timezone="Asia/Tokyo",
        calendars=[
            CalendarPolicy(
                id="primary",
                label="main",
                allow_create=True,
                allow_update=True,
            )
        ],
    )


def test_calendar_by_id_primary() -> None:
    cal = calendar_by_id(_writable_policy(), "primary")
    assert cal.id == "primary"


def test_calendar_by_id_missing_raises() -> None:
    with pytest.raises(CalendarWriteError, match="not configured"):
        calendar_by_id(_writable_policy(), "unknown-cal")


def test_require_create_denied() -> None:
    cal = CalendarPolicy(id="primary", allow_create=False)
    with pytest.raises(CalendarWriteError, match="allow_create=false"):
        require_create_allowed(cal)


def test_require_update_denied() -> None:
    cal = CalendarPolicy(id="primary", allow_update=False)
    with pytest.raises(CalendarWriteError, match="allow_update=false"):
        require_update_allowed(cal)


def test_default_smoke_slot_tomorrow() -> None:
    start, end = default_smoke_slot(timezone="Asia/Tokyo", day_offset=1)
    assert start.hour == 10 and start.minute == 0
    assert (end - start).total_seconds() == 30 * 60


def test_run_write_smoke_dry_run() -> None:
    service = MagicMock()
    created, patched = run_write_smoke(service, _writable_policy(), dry_run=True)
    assert created is None and patched is None
    service.events.assert_not_called()
