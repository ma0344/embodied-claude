#!/usr/bin/env python3
"""Score STM rows for MEM-5 (prototype). Reads ~/.claude/sociality/social.db."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SOCIAL_CORE_SRC = _ROOT / "sociality-mcp" / "packages" / "social-core" / "src"
if str(_SOCIAL_CORE_SRC) not in sys.path:
    sys.path.insert(0, str(_SOCIAL_CORE_SRC))

from social_core.stm import StmEntry  # noqa: E402
from social_core.stm_scoring import score_stm_batch  # noqa: E402


def _load_entries(db_path: Path, *, local_day: str | None, undreamed_only: bool) -> tuple[list[StmEntry], dict[str, str]]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    where = ["1=1"]
    args: list[object] = []
    if local_day:
        where.append("local_day = ?")
        args.append(local_day)
    if undreamed_only:
        where.append("dreamed_at IS NULL")
    sql = f"""
        SELECT entry_id, ts, local_day, person_id, source, kind, summary,
               session_id, experience_id, turn_index, importance, dreamed_at, created_at,
               metadata_json
        FROM stm_entries
        WHERE {' AND '.join(where)}
        ORDER BY local_day, ts
    """
    rows = con.execute(sql, tuple(args)).fetchall()
    entries: list[StmEntry] = []
    meta: dict[str, str] = {}
    for row in rows:
        entries.append(
            StmEntry(
                entry_id=row["entry_id"],
                ts=row["ts"],
                local_day=row["local_day"],
                person_id=row["person_id"],
                source=row["source"],
                kind=row["kind"],
                summary=row["summary"],
                session_id=row["session_id"],
                experience_id=row["experience_id"],
                turn_index=row["turn_index"],
                importance=int(row["importance"]),
                dreamed_at=row["dreamed_at"],
                created_at=row["created_at"],
            )
        )
        meta[row["entry_id"]] = row["metadata_json"] or "{}"
    return entries, meta


def main() -> int:
    parser = argparse.ArgumentParser(description="MEM-5 STM scoring prototype")
    parser.add_argument("--db", type=Path, default=Path.home() / ".claude/sociality/social.db")
    parser.add_argument("--day", help="local_day filter (YYYY-MM-DD)")
    parser.add_argument("--undreamed-only", action="store_true", default=True)
    parser.add_argument("--all", dest="undreamed_only", action="store_false")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if not args.db.is_file():
        print(f"DB not found: {args.db}", file=sys.stderr)
        return 1

    entries, meta = _load_entries(args.db, local_day=args.day, undreamed_only=args.undreamed_only)
    scores = score_stm_batch(entries, metadata_by_id=meta)

    if args.json:
        print(json.dumps([s.to_dict() for s in scores], ensure_ascii=False, indent=2))
        return 0

    for s in scores:
        print(f"{s.entry_id}  {s.decision:6}  score={s.promote_score:.2f}  E={s.emotion_score:.2f} I={s.interest_score:.2f} F={s.frequency_score:.2f}")
        print(f"  kind={s.kind} source={s.source} topics={s.topics} emotion={s.inferred_emotion}")
        print(f"  -> {s.reason}")
        print(f"  | {s.summary_preview}")
        print()
    promote = sum(1 for s in scores if s.decision == "promote")
    merge = sum(1 for s in scores if s.decision == "merge")
    hold = sum(1 for s in scores if s.decision == "hold")
    skip = sum(1 for s in scores if s.decision == "skip")
    print(f"Summary: promote={promote} merge={merge} hold={hold} skip={skip} (n={len(scores)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
