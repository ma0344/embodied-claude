#!/usr/bin/env python3
"""Purge LW-READ literary passage dumps from memory.db (LTM).

READ used to http_remember full Aozora passages into conversational LTM,
which polluted compose [relevant_memories]. Experience / reading bookmark
remain; this only removes LTM rows matching literary encode prefixes.

Usage:
  python scripts/purge-literary-ltm.py --dry-run
  python scripts/purge-literary-ltm.py
  python scripts/purge-literary-ltm.py --db PATH

After apply: restart memory-mcp so in-memory Hopfield reloads.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Finite encode prefixes from read_aozora_passage / related dumps (not open NL).
_LIKE_PATTERNS = (
    "青空文庫で読んだ%",
    "青空『%",
    "（青空を読んだあと%",
)


def default_db() -> Path:
    return Path.home() / ".claude" / "memories" / "memory.db"


def list_matches(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    where = " OR ".join("content LIKE ?" for _ in _LIKE_PATTERNS)
    return list(
        conn.execute(
            f"SELECT id, timestamp, category, importance, substr(content, 1, 80) AS snip "
            f"FROM memories WHERE {where} ORDER BY timestamp DESC",
            _LIKE_PATTERNS,
        )
    )


def purge(conn: sqlite3.Connection, ids: list[str]) -> int:
    conn.execute("PRAGMA foreign_keys = ON")
    deleted = 0
    for memory_id in ids:
        cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        deleted += cur.rowcount
    conn.commit()
    return deleted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="memory.db path (default: ~/.claude/memories/memory.db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List matches only; do not delete",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip copying memory.db before delete",
    )
    args = parser.parse_args()
    db_path = args.db or default_db()
    if not db_path.is_file():
        print(f"memory.db not found: {db_path}")
        return 1

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = list_matches(conn)
        print(f"db: {db_path}")
        print(f"matches: {len(rows)}")
        for row in rows[:40]:
            snip = (row["snip"] or "").replace("\u2014", "—").encode(
                "cp932", errors="replace"
            ).decode("cp932")
            print(f"  {row['id']}  {row['timestamp']}  [{row['category']}]  {snip}…")
        if len(rows) > 40:
            print(f"  … +{len(rows) - 40} more")

        if args.dry_run:
            print("dry-run: no deletes")
            return 0
        if not rows:
            print("nothing to delete")
            return 0

        if not args.no_backup:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            backup = (
                Path.home()
                / ".claude"
                / "backups"
                / f"purge-literary-ltm-{ts}"
                / "memory.db"
            )
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(db_path, backup)
            print(f"backup: {backup}")

        n = purge(conn, [str(r["id"]) for r in rows])
        print(f"deleted: {n}")
        print("NOTE: restart memory-mcp so Hopfield / working memory reload.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
