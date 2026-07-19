#!/usr/bin/env python3
"""Purge desire / VISION / BIO-8d / gateway_turn_context telemetry from memory.db.

Finite agent markers only — does not match open NL. Meal cards
(``を食べた記録がある``) and conversation episodes without these markers stay.

Buckets:
  1. VISION — content contains one of:
       ``=== VISION_CAPTION`` / ``Captured image at `` /
       ``VISION_DESCRIBE_FAILED`` / ``--- Center View``
  2. desire telemetry — content LIKE ``[desire:%`` (leading)
  3. BIO-8d push — starts with ``体の調子がおかしいで。`` and has
       simultaneous-failure + ``見てもらえる？`` (same shape as somatic_surface)
  4. gateway_turn_context fragments — content LIKE ``%[gateway_turn_context%``

Usage (dry-run is the default):
  python scripts/purge-telemetry-ltm.py
  python scripts/purge-telemetry-ltm.py --db PATH
  python scripts/purge-telemetry-ltm.py --apply

After --apply: restart memory-mcp so in-memory Hopfield / Chroma reload if used.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Finite markers only (not open NL cues).
_VISION_SUBSTRINGS = (
    "=== VISION_CAPTION",
    "Captured image at ",
    "VISION_DESCRIBE_FAILED",
    "--- Center View",
)

_DESIRE_PREFIX = "[desire:%"
_GATEWAY_FRAGMENT = "%[gateway_turn_context%"

_BIO8D_START = "体の調子がおかしいで。"
_BIO8D_ASK = "見てもらえる？"
_BIO8D_SIMUL = ("が同時にダメかも", "複数の感覚が同時にダメかも")


def default_db() -> Path:
    return Path.home() / ".claude" / "memories" / "memory.db"


def _vision_where() -> tuple[str, tuple[str, ...]]:
    clauses = " OR ".join("content LIKE ?" for _ in _VISION_SUBSTRINGS)
    params = tuple(f"%{m}%" for m in _VISION_SUBSTRINGS)
    return clauses, params


def _is_bio8d_push(content: str) -> bool:
    text = (content or "").strip()
    if not text.startswith(_BIO8D_START):
        return False
    if _BIO8D_ASK not in text:
        return False
    return any(m in text for m in _BIO8D_SIMUL)


def classify_bucket(content: str) -> str | None:
    """Return purge bucket name, or None if the row must be kept."""
    text = content or ""
    stripped = text.strip()
    if any(m in text for m in _VISION_SUBSTRINGS):
        return "vision"
    if stripped.startswith("[desire:"):
        return "desire"
    if _is_bio8d_push(text):
        return "bio8d"
    if "[gateway_turn_context" in text:
        return "gateway_turn_context"
    return None


def list_matches(conn: sqlite3.Connection) -> list[tuple[str, sqlite3.Row]]:
    """Return (bucket, row) for purge candidates (deduped by id)."""
    vision_sql, vision_params = _vision_where()
    sql = f"""
        SELECT id, timestamp, category, importance, content,
               substr(content, 1, 96) AS snip
        FROM memories
        WHERE ({vision_sql})
           OR content LIKE ?
           OR content LIKE ?
        ORDER BY timestamp DESC
    """
    params = (*vision_params, _DESIRE_PREFIX, _GATEWAY_FRAGMENT)
    rows = list(conn.execute(sql, params))

    # BIO-8d is rare; scan startswith prefix then filter in Python
    # (finite template — avoid open NL LIKE).
    bio_rows = list(
        conn.execute(
            """
            SELECT id, timestamp, category, importance, content,
                   substr(content, 1, 96) AS snip
            FROM memories
            WHERE content LIKE ?
            ORDER BY timestamp DESC
            """,
            (f"{_BIO8D_START}%",),
        )
    )

    by_id: dict[str, tuple[str, sqlite3.Row]] = {}
    for row in rows:
        bucket = classify_bucket(str(row["content"] or ""))
        if bucket is None:
            continue
        by_id[str(row["id"])] = (bucket, row)
    for row in bio_rows:
        if not _is_bio8d_push(str(row["content"] or "")):
            continue
        mid = str(row["id"])
        if mid not in by_id:
            by_id[mid] = ("bio8d", row)
    return list(by_id.values())


def count_by_bucket(matches: list[tuple[str, sqlite3.Row]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for bucket, _ in matches:
        out[bucket] = out.get(bucket, 0) + 1
    return out


def purge(conn: sqlite3.Connection, ids: list[str]) -> int:
    conn.execute("PRAGMA foreign_keys = ON")
    deleted = 0
    for memory_id in ids:
        cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        deleted += cur.rowcount
    conn.commit()
    return deleted


def _safe_snip(text: str) -> str:
    return (text or "").replace("\n", " ").encode("cp932", errors="replace").decode(
        "cp932"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="memory.db path (default: ~/.claude/memories/memory.db)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete matching rows (default is dry-run)",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip copying memory.db before delete (apply only)",
    )
    args = parser.parse_args(argv)
    db_path = (args.db or default_db()).expanduser()
    if not db_path.is_file():
        print(f"memory.db not found: {db_path}")
        return 1

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        matches = list_matches(conn)
        counts = count_by_bucket(matches)
        print(f"db: {db_path}")
        print(f"matches: {len(matches)}")
        for bucket in ("vision", "desire", "bio8d", "gateway_turn_context"):
            if bucket in counts:
                print(f"  {bucket}: {counts[bucket]}")
        for bucket, row in matches[:40]:
            snip = _safe_snip(str(row["snip"] or ""))
            print(
                f"  [{bucket}] {row['id']}  {row['timestamp']}  "
                f"[{row['category']}]  {snip}…"
            )
        if len(matches) > 40:
            print(f"  … +{len(matches) - 40} more")

        if not args.apply:
            print("dry-run: no deletes (pass --apply to delete)")
            return 0
        if not matches:
            print("nothing to delete")
            return 0

        backup_path: Path | None = None
        if not args.no_backup:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            backup_path = db_path.parent / f"memory.db.purge-telemetry-{ts}.bak"
            shutil.copy2(db_path, backup_path)
            print(f"backup: {backup_path}")

        n = purge(conn, [str(r["id"]) for _, r in matches])
        print(f"deleted: {n}")
        for bucket, c in sorted(counts.items()):
            print(f"  deleted_{bucket}: {c}")
        print(
            "NOTE: restart memory-mcp so Hopfield / working memory reload; "
            "if Chroma still indexes old docs, re-ingest or rebuild as needed."
        )
        if backup_path is not None:
            print(f"backup_path: {backup_path}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
