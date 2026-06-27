"""CLI — OAuth consent and calendar smoke (GAPI-prep-1 / prep-2)."""

from __future__ import annotations

import argparse
import sys

from presence_ui.gapi.auth import GoogleAuthError, get_calendar_service, run_oauth_consent
from presence_ui.gapi.calendar_client import format_calendar_prefetch_block, list_events_in_prefetch_window
from presence_ui.gapi.calendar_writes import CalendarWriteError, run_write_smoke
from presence_ui.gapi.policy import load_google_policy
from presence_ui.gapi.scopes import DEFAULT_PREP_SCOPES


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
