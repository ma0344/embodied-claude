#!/usr/bin/env python3
"""Close open_loops that were mistakenly created from agent dialogue."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_PKG = _REPO / "sociality-mcp" / "packages" / "relationship-mcp" / "src"
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

from relationship_mcp.store import RelationshipStore  # noqa: E402


def is_noise_topic(topic: str) -> bool:
    compact = topic.strip()
    if not compact:
        return True
    if len(compact) > 40:
        return True
    if "うち、" in compact or "こより" in compact:
        return True
    if compact.count("、") >= 2:
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--person-id", default="ma")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    store = RelationshipStore()
    try:
        rows = store.db.fetchall(
            """
            SELECT loop_id, topic
            FROM open_loops
            WHERE person_id = ? AND status = 'open'
            ORDER BY updated_at DESC
            """,
            (args.person_id,),
        )
        noise = [(row[0], row[1]) for row in rows if is_noise_topic(str(row[1]))]
        if not noise:
            print("No noise open loops to close.")
            return 0

        print(f"Found {len(noise)} noise open loop(s) for {args.person_id}:")
        for loop_id, topic in noise:
            preview = topic[:60] + ("…" if len(topic) > 60 else "")
            print(f"  - {loop_id}: {preview}")

        if args.dry_run:
            print("(dry-run - no changes)")
            return 0

        with store.db.transaction() as conn:
            for loop_id, _ in noise:
                conn.execute(
                    "UPDATE open_loops SET status = 'closed' WHERE loop_id = ?",
                    (loop_id,),
                )
        print(f"Closed {len(noise)} loop(s).")
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
