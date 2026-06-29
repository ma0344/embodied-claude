"""Remove or sanitize interpretation_shifts polluted with cheerleader acknowledged text.

Dry-run by default:
  python scripts/cleanup-shift-cheerleader.py
Apply:
  python scripts/cleanup-shift-cheerleader.py --apply
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

DEFAULT_DB = Path.home() / ".claude" / "sociality" / "social.db"

_CHEERLEADER_RE = re.compile(
    r"(?:"
    r"応援して|楽しみ(?:にして|や)|頑張って|いつでも言うて|何か(?:手伝|あったら)|"
    r"お疲れさ|無理せんと|適度に休|根詰めしすぎ|ペースで進め|ずっと応援"
    r")"
)


def strip_acknowledged_cheerleader_suffix(new_interpretation: str) -> str | None:
    """Return sanitized new_interpretation, or None if row should be deleted."""
    text = (new_interpretation or "").strip()
    if not text:
        return None
    if "→ acknowledged:" not in text and "→ ack:" not in text:
        if _CHEERLEADER_RE.search(text):
            return None
        return text
    if _CHEERLEADER_RE.search(text):
        return None
    user_part = re.split(r"\s*→\s*(?:ack(?:nowledged)?(?:\s*:)?\s*)", text, maxsplit=1)[0].strip()
    return user_part[:400] if user_part else None


def _classify_row(new_interpretation: str) -> str:
    sanitized = strip_acknowledged_cheerleader_suffix(new_interpretation)
    if sanitized is None:
        return "delete"
    if sanitized != (new_interpretation or "").strip():
        return "sanitize"
    return "keep"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete/sanitize cheerleader-polluted interpretation_shifts",
    )
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    if not args.db.is_file():
        print(f"DB not found: {args.db}")
        return 1

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT shift_id, ts, topic, new_interpretation
        FROM interpretation_shifts
        ORDER BY ts DESC
        """
    ).fetchall()

    to_delete: list[str] = []
    to_sanitize: list[tuple[str, str]] = []

    for row in rows:
        new_text = str(row["new_interpretation"] or "")
        action = _classify_row(new_text)
        if action == "delete":
            to_delete.append(str(row["shift_id"]))
        elif action == "sanitize":
            sanitized = strip_acknowledged_cheerleader_suffix(new_text)
            assert sanitized is not None
            to_sanitize.append((str(row["shift_id"]), sanitized))

    print(f"DB: {args.db}")
    print(f"Total interpretation_shifts: {len(rows)}")
    print(f"Delete (cheerleader / unsalvageable): {len(to_delete)}")
    for shift_id in to_delete[:8]:
        match = next(r for r in rows if r["shift_id"] == shift_id)
        snippet = str(match["new_interpretation"])[:100].replace("\n", " ")
        print(f"  - {shift_id} {match['ts']}: {snippet}…")
    if len(to_delete) > 8:
        print(f"  ... and {len(to_delete) - 8} more")

    print(f"Sanitize (strip acknowledged suffix): {len(to_sanitize)}")
    for shift_id, sanitized in to_sanitize[:5]:
        print(f"  - {shift_id}: → {sanitized[:80]}…")

    kept = len(rows) - len(to_delete) - len(to_sanitize)
    print(f"Unchanged: {kept}")

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to write.")
        return 0

    for shift_id in to_delete:
        conn.execute("DELETE FROM interpretation_shifts WHERE shift_id = ?", (shift_id,))
    for shift_id, sanitized in to_sanitize:
        conn.execute(
            "UPDATE interpretation_shifts SET new_interpretation = ? WHERE shift_id = ?",
            (sanitized, shift_id),
        )
    conn.commit()
    print(
        f"\nApplied: deleted {len(to_delete)}, sanitized {len(to_sanitize)} interpretation_shifts."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
