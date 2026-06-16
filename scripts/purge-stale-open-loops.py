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
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_REPO = Path(__file__).resolve().parents[1]
_REL = _REPO / "sociality-mcp" / "packages" / "relationship-mcp" / "src"
_CORE = _REPO / "sociality-mcp" / "packages" / "social-core" / "src"
for _p in (_REL, _CORE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from relationship_mcp.date_resolution import as_of_date, is_stale  # noqa: E402
from relationship_mcp.store import RelationshipStore  # noqa: E402


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
        as_of_ts = datetime.combine(as_of, datetime.min.time(), tzinfo=ZoneInfo(args.timezone))
    else:
        as_of_ts = datetime.now(ZoneInfo(args.timezone))
        as_of = as_of_date(as_of_ts=as_of_ts.isoformat(), tz_name=args.timezone)

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
        for loop_id, topic, updated_at, _detail_json in rows:
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

        closed = store.close_stale_open_loops(
            person_id=args.person_id,
            as_of=as_of_ts.isoformat(),
            timezone=args.timezone,
            include_today=args.include_today,
        )
        print(f"Closed {len(closed)} stale loop(s).")
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
