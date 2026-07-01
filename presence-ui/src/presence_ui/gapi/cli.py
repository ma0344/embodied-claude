"""CLI — OAuth consent and calendar smoke (GAPI-prep-1 / prep-2)."""

from __future__ import annotations

import argparse
import sys

from presence_ui.gapi.auth import GoogleAuthError, get_calendar_service, run_oauth_consent
from presence_ui.gapi.calendar_client import format_calendar_prefetch_block, list_events_in_prefetch_window
from presence_ui.gapi.calendar_writes import CalendarWriteError, run_write_smoke
from presence_ui.gapi.policy import load_google_policy
from presence_ui.gapi.scopes import DEFAULT_PREP_SCOPES

_DEFAULT_READ_WINDOW_UTTERANCES = (
    "今日の予定は？",
    "来週の予定は？",
    "来月の予定は？",
    "昨日の予定はどうなっていた？",
    "来週中に何かある？",
)


def consent_main() -> int:
    parser = argparse.ArgumentParser(description="Google OAuth consent for GAPI (Calendar read)")
    parser.add_argument(
        "--scope",
        choices=("readonly", "events"),
        default="readonly",
        help="readonly=GAPI-2, events=GAPI-7 (includes read)",
    )
    args = parser.parse_args()
    scopes: tuple[str, ...]
    if args.scope == "events":
        from presence_ui.gapi.scopes import CALENDAR_EVENTS

        scopes = (CALENDAR_EVENTS,)
    else:
        scopes = DEFAULT_PREP_SCOPES

    try:
        run_oauth_consent(scopes=scopes)
    except GoogleAuthError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print("Consent OK. Next: uv run gapi-calendar-smoke")
    return 0


def list_smoke_main() -> int:
    parser = argparse.ArgumentParser(description="List Calendar events (today+tomorrow smoke)")
    parser.add_argument("--prefetch", action="store_true", help="Print [calendar_prefetch] block")
    args = parser.parse_args()

    policy = load_google_policy()
    if not policy.enabled:
        print("gapi-policy: google.enabled is false or policy file missing.", file=sys.stderr)
        return 1
    if not policy.readable_calendars():
        print("gapi-policy: no readable calendars configured.", file=sys.stderr)
        return 1

    try:
        service = get_calendar_service()
        events = list_events_in_prefetch_window(service, policy)
    except GoogleAuthError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Calendar API error: {exc}", file=sys.stderr)
        return 1

    if args.prefetch:
        print(format_calendar_prefetch_block(policy, events))
        return 0

    print(f"timezone={policy.timezone} range={policy.prefetch_day_range}")
    print(f"events={len(events)}")
    for event in events:
        loc = f" @ {event.location}" if event.location else ""
        print(f"  [{event.calendar_label}] {event.start}  {event.summary}{loc}")
    return 0


def write_smoke_main() -> int:
    parser = argparse.ArgumentParser(
        description="Create + patch a [gapi-smoke] calendar event (GAPI-prep-2)"
    )
    parser.add_argument("--calendar-id", default="primary", help="Target calendar id")
    parser.add_argument("--dry-run", action="store_true", help="Policy check only, no API writes")
    args = parser.parse_args()

    policy = load_google_policy()
    if not policy.enabled:
        print("gapi-policy: google.enabled is false or policy file missing.", file=sys.stderr)
        return 1

    try:
        service = get_calendar_service()
        created, patched = run_write_smoke(
            service,
            policy,
            calendar_id=args.calendar_id,
            dry_run=args.dry_run,
        )
    except (GoogleAuthError, CalendarWriteError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Calendar API error: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        return 0

    assert created is not None and patched is not None
    print("create OK")
    print(f"  id={created.event_id}")
    print(f"  {created.start} -> {created.end}")
    if created.html_link:
        print(f"  link={created.html_link}")
    print("patch OK (+1h)")
    print(f"  {patched.start} -> {patched.end}")
    print("Note: delete API is not exposed — remove [gapi-smoke] events manually if needed.")
    return 0


def read_window_smoke_main() -> int:
    """GAPI-2b — utterance-dependent read window + Calendar list (ma-home E2E)."""
    import os
    import re

    parser = argparse.ArgumentParser(
        description="Resolve prefetch window from utterance and list events (GAPI-2b)"
    )
    parser.add_argument(
        "--utterance",
        action="append",
        dest="utterances",
        help="Test utterance (repeatable). Default: built-in matrix.",
    )
    parser.add_argument(
        "--show-block",
        action="store_true",
        help="Print full [calendar_prefetch] block for each utterance",
    )
    parser.add_argument(
        "--no-api",
        action="store_true",
        help="Resolve window only — skip Calendar API",
    )
    args = parser.parse_args()

    os.environ.setdefault("PRESENCE_GAPI_READ_WINDOW_E4B", "0")
    utterances = args.utterances or list(_DEFAULT_READ_WINDOW_UTTERANCES)

    policy = load_google_policy()
    if not policy.enabled:
        print("gapi-policy: google.enabled is false or policy file missing.", file=sys.stderr)
        return 1
    if not policy.readable_calendars():
        print("gapi-policy: no readable calendars configured.", file=sys.stderr)
        return 1

    from presence_ui.gateway.calendar_prefetch import fetch_calendar_prefetch_sync

    failures = 0
    for utterance in utterances:
        print(f"\n=== {utterance} ===")
        if args.no_api:
            from presence_ui.gateway.calendar_read_window import resolve_prefetch_window
            from zoneinfo import ZoneInfo

            tz = ZoneInfo(policy.timezone)
            anchor = __import__("datetime").datetime.now(tz).isoformat(timespec="seconds")
            window = resolve_prefetch_window(
                utterance,
                anchor_iso=anchor,
                tz_name=policy.timezone,
                fallback_day_range=policy.prefetch_day_range,
            )
            print(f"resolution={window.resolution} range={window.range_label}")
            if window.resolution == "ambiguous":
                print(f"ambiguous={','.join(window.ambiguous_phrases)}")
            continue

        block, status = fetch_calendar_prefetch_sync(utterance)
        range_match = re.search(r"^range=(.+)$", block, re.M)
        resolution_match = re.search(r"^resolution=(.+)$", block, re.M)
        event_lines = [
            line
            for line in block.splitlines()
            if line and not line.startswith("[") and not line.startswith("---")
        ]
        event_count = sum(
            1
            for line in event_lines
            if "|" in line and not line.startswith("timezone=") and not line.startswith("status=")
        )
        print(f"status={status}")
        if range_match:
            print(f"range={range_match.group(1).strip()}")
        if resolution_match:
            print(f"resolution={resolution_match.group(1).strip()}")
        print(f"events={event_count}")
        if status in {"error", "disabled"}:
            failures += 1
        if args.show_block:
            print(block)
    return 1 if failures else 0
