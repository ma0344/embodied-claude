#!/usr/bin/env python3
"""Close open_loops whose relative-date topics (明日, today, …) are past due.

Open loops store the utterance text as topic without resolving calendar dates.
A loop created on 2026-06-14 with 「明日は10時から会議」 refers to 2026-06-15;
from 2026-06-16 onward it is stale but remains status=open unless closed.

Usage:
  cd sociality-mcp/packages/relationship-mcp
  uv run python ../../../scripts/purge-stale-open-loops.py --dry-run
  uv run python ../../../scripts/purge-stale-open-loops.py --include-today
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

_REPO = Path(__file__).resolve().parents[1]
_REL = _REPO / "sociality-mcp" / "packages" / "relationship-mcp" / "src"
_CORE = _REPO / "sociality-mcp" / "packages" / "social-core" / "src"
for _p in (_REL, _CORE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from relationship_mcp.store import RelationshipStore  # noqa: E402

_RELATIVE_MARKERS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"明後日|あさって|day after tomorrow", re.I), 2),
    (re.compile(r"明日|tomorrow", re.I), 1),
    (re.compile(r"今日|きょう|today", re.I), 0),
]


def _parse_updated_day(updated_at: str, tz: ZoneInfo) -> date:
    raw = updated_at.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(tz).date()


def resolve_relative_date(*, topic: str, updated_at: str, tz_name: str) -> date | None:
    """Return the calendar day the topic refers to, or None if no relative marker."""
    tz = ZoneInfo(tz_name)
    base = _parse_updated_day(updated_at, tz)
    for pattern, offset_days in _RELATIVE_MARKERS:
        if pattern.search(topic):
            return base + timedelta(days=offset_days)
    return None


def is_stale(
    *,
    topic: str,
    updated_at: str,
    tz_name: str,
    as_of: date,
    include_today: bool,
) -> date | None:
    """If stale, return the resolved date; else None."""
    resolved = resolve_relative_date(topic=topic, updated_at=updated_at, tz_name=tz_name)
    if resolved is None:
        return None
    if resolved < as_of or (include_today and resolved == as_of):
        return resolved
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--person-id", default="ma")
    parser.add_argument("--timezone", default="Asia/Tokyo")
    parser.add_argument(
        "--as-of",
        default="",
        help="Treat this YYYY-MM-DD as today (default: now in --timezone)",
    )
    parser.add_argument(
        "--include-today",
        action="store_true",
        help="Also close loops whose resolved day is today (manual cleanup on meeting day)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.as_of:
        as_of = date.fromisoformat(args.as_of)
    else:
        as_of = datetime.now(ZoneInfo(args.timezone)).date()

    store = RelationshipStore()
    try:
        rows = store.db.fetchall(
            """
            SELECT loop_id, topic, updated_at, detail_json
            FROM open_loops
            WHERE person_id = ? AND status = 'open'
            ORDER BY updated_at DESC
            """,
            (args.person_id,),
        )
        stale: list[tuple[str, str, date]] = []
        for loop_id, topic, updated_at, detail_json in rows:
            passed = is_stale(
                topic=str(topic),
                updated_at=str(updated_at),
                tz_name=args.timezone,
                as_of=as_of,
                include_today=args.include_today,
            )
            if passed is not None:
                stale.append((str(loop_id), str(topic), passed))

        if not stale:
            print(f"No stale open loops for {args.person_id} (as_of={as_of}, tz={args.timezone}).")
            return 0

        print(
            f"Found {len(stale)} stale open loop(s) for {args.person_id} "
            f"(as_of={as_of}, tz={args.timezone}):"
        )
        for loop_id, topic, resolved in stale:
            preview = topic[:72] + ("…" if len(topic) > 72 else "")
            print(f"  - {loop_id} (resolved {resolved}): {preview}")

        if args.dry_run:
            print("(dry-run - no changes)")
            return 0

        with store.db.transaction() as conn:
            for loop_id, topic, resolved in stale:
                detail = {
                    "kind": "stale",
                    "reason": "relative_date_passed",
                    "resolved_date": resolved.isoformat(),
                    "source_topic": topic[:200],
                }
                conn.execute(
                    """
                    UPDATE open_loops
                    SET status = 'closed', detail_json = ?
                    WHERE loop_id = ?
                    """,
                    (json.dumps(detail, ensure_ascii=False), loop_id),
                )
        print(f"Closed {len(stale)} stale loop(s).")
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
