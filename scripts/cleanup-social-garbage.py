"""Remove legacy social.db garbage from pre-fix interpretation_shift / open_loop ingest.

Dry-run by default:
  python scripts/cleanup-social-garbage.py
Apply:
  python scripts/cleanup-social-garbage.py --apply
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

DEFAULT_DB = Path.home() / ".claude" / "sociality" / "social.db"

# Synthetic topic from compose boundary_hints mistaken as user corrections (fixed 2026-06-20).
_GARBAGE_SHIFT_TOPIC = "availability is ambivalent; prefer bounded replies"

_NOISE_OPEN_LOOP = re.compile(
    r"ありがと|調べてくれた|教えてくれた|うち、|こより",
    re.IGNORECASE,
)


def _is_noise_open_loop(topic: str) -> bool:
    compact = topic.strip()
    if not compact:
        return True
    if "うち、" in compact or "こより" in compact:
        return True
    if "ありがと" in compact and ("調べてくれた" in compact or "教えてくれた" in compact):
        return True
    if compact.endswith("ね") and "、調べ" in compact:
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean social.db interpretation_shift / open_loop noise")
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    if not args.db.is_file():
        print(f"DB not found: {args.db}")
        return 1

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    shift_rows = conn.execute(
        "SELECT shift_id, ts, topic FROM interpretation_shifts WHERE topic = ?",
        (_GARBAGE_SHIFT_TOPIC,),
    ).fetchall()

    open_rows = conn.execute(
        "SELECT loop_id, topic, updated_at FROM open_loops WHERE person_id = 'ma' AND status = 'open'",
    ).fetchall()
    noise_loops = [r for r in open_rows if _is_noise_open_loop(str(r["topic"]))]

    print(f"DB: {args.db}")
    print(f"Garbage interpretation_shifts: {len(shift_rows)}")
    for r in shift_rows[:5]:
        print(f"  - {r['shift_id']} {r['ts']}")
    if len(shift_rows) > 5:
        print(f"  ... and {len(shift_rows) - 5} more")

    print(f"Noise open_loops to close: {len(noise_loops)}")
    for r in noise_loops:
        print(f"  - {r['loop_id']}: {r['topic'][:70]}")

    kept = [r for r in open_rows if r not in noise_loops]
    if kept:
        print(f"Open loops kept: {len(kept)}")
        for r in kept:
            print(f"  - {r['loop_id']}: {r['topic'][:70]}")

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to write.")
        return 0

    if shift_rows:
        conn.execute(
            "DELETE FROM interpretation_shifts WHERE topic = ?",
            (_GARBAGE_SHIFT_TOPIC,),
        )
    for r in noise_loops:
        conn.execute(
            """
            UPDATE open_loops
            SET status = 'closed', updated_at = datetime('now')
            WHERE loop_id = ?
            """,
            (r["loop_id"],),
        )
    conn.commit()
    print(f"\nApplied: deleted {len(shift_rows)} shifts, closed {len(noise_loops)} open loops.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
