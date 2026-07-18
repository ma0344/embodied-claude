#!/usr/bin/env python3
"""Purge LW-READ literary dumps from social.db + clean overnight digest.

Targets (agent encode prefixes only):
  - stm_entries.summary
  - agent_experiences.summary
  - private_reflections.body / title
  - last_dream_digest.json summary lines + literary inner_voice_summary

Usage:
  python scripts/purge-literary-social.py --dry-run
  python scripts/purge-literary-social.py
  python scripts/purge-literary-social.py --reflections-only
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_CORE = _REPO / "sociality-mcp" / "packages" / "social-core" / "src"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from social_core.literary_surface import (  # noqa: E402
    LITERARY_AGENT_PREFIXES,
    is_literary_overnight_contaminated,
)

_LIKE_PATTERNS = tuple(f"{p}%" for p in LITERARY_AGENT_PREFIXES)


def default_db() -> Path:
    return Path.home() / ".claude" / "sociality" / "social.db"


def digest_path() -> Path:
    return Path.home() / ".claude" / "presence-ui" / "last_dream_digest.json"


def _summary_where() -> str:
    return " OR ".join("summary LIKE ?" for _ in _LIKE_PATTERNS)


def _reflection_where() -> tuple[str, tuple[str, ...]]:
    clauses: list[str] = []
    params: list[str] = []
    for pattern in _LIKE_PATTERNS:
        clauses.append("body LIKE ?")
        params.append(pattern)
        clauses.append("title LIKE ?")
        params.append(pattern)
    return " OR ".join(clauses), tuple(params)


def list_stm(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            f"SELECT entry_id, ts, kind, substr(summary, 1, 72) AS snip "
            f"FROM stm_entries WHERE {_summary_where()} ORDER BY ts DESC",
            _LIKE_PATTERNS,
        )
    )


def list_experiences(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            f"SELECT experience_id, ts, kind, substr(summary, 1, 72) AS snip "
            f"FROM agent_experiences WHERE {_summary_where()} ORDER BY ts DESC",
            _LIKE_PATTERNS,
        )
    )


def list_reflections(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    where, params = _reflection_where()
    return list(
        conn.execute(
            f"SELECT reflection_id, ts, substr(title, 1, 40) AS t, "
            f"substr(body, 1, 72) AS snip "
            f"FROM private_reflections WHERE {where} ORDER BY ts DESC",
            params,
        )
    )


def purge(
    conn: sqlite3.Connection,
    *,
    stm_ids: list[str],
    exp_ids: list[str],
    reflection_ids: list[str],
) -> dict[str, int]:
    deleted = {"stm": 0, "experiences": 0, "private_reflections": 0}
    for eid in stm_ids:
        cur = conn.execute("DELETE FROM stm_entries WHERE entry_id = ?", (eid,))
        deleted["stm"] += cur.rowcount
    for xid in exp_ids:
        cur = conn.execute(
            "DELETE FROM agent_experiences WHERE experience_id = ?", (xid,)
        )
        deleted["experiences"] += cur.rowcount
    for rid in reflection_ids:
        cur = conn.execute(
            "DELETE FROM private_reflections WHERE reflection_id = ?", (rid,)
        )
        deleted["private_reflections"] += cur.rowcount
    conn.commit()
    return deleted


def rebuild_digest() -> str:
    """Strip literary digest lines and clear contaminated overnight inner voice."""
    path = digest_path()
    if not path.is_file():
        return "no digest file"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"digest read failed: {exc}"

    notes: list[str] = []
    summary = str(payload.get("summary") or "")
    if summary:
        lines = summary.splitlines()
        kept: list[str] = []
        dropped = 0
        for line in lines:
            body = line.lstrip("- ").strip()
            if ") " in body:
                body = body.split(") ", 1)[-1]
            if any(body.startswith(p) for p in LITERARY_AGENT_PREFIXES):
                dropped += 1
                continue
            if is_literary_overnight_contaminated(body):
                dropped += 1
                continue
            kept.append(line)
        if dropped:
            payload["summary"] = "\n".join(kept)
            notes.append(f"digest lines stripped={dropped}")
        else:
            notes.append("digest lines unchanged")

    iv = str(payload.get("inner_voice_summary") or "")
    if iv and is_literary_overnight_contaminated(iv):
        payload["inner_voice_summary"] = None
        notes.append("inner_voice_summary cleared (literary)")
    elif iv:
        notes.append("inner_voice_summary kept")
    else:
        notes.append("inner_voice_summary empty")

    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return "; ".join(notes)


def _print_snip(label: str, snip: str) -> str:
    return (snip or "").encode("cp932", errors="replace").decode("cp932")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--keep-experiences",
        action="store_true",
        help="Do not delete agent_experiences",
    )
    parser.add_argument(
        "--keep-stm",
        action="store_true",
        help="Do not delete stm_entries",
    )
    parser.add_argument(
        "--reflections-only",
        action="store_true",
        help="Only private_reflections + digest/inner_voice",
    )
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument("--no-digest", action="store_true")
    args = parser.parse_args()
    db_path = args.db or default_db()
    if not db_path.is_file():
        print(f"social.db not found: {db_path}")
        return 1

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        stm_rows: list[sqlite3.Row] = []
        exp_rows: list[sqlite3.Row] = []
        if not args.reflections_only:
            if not args.keep_stm:
                stm_rows = list_stm(conn)
            if not args.keep_experiences:
                exp_rows = list_experiences(conn)
        ref_rows = list_reflections(conn)

        print(f"db: {db_path}")
        print(f"stm matches: {len(stm_rows)}")
        print(f"experience matches: {len(exp_rows)}")
        print(f"private_reflections matches: {len(ref_rows)}")
        for row in stm_rows[:8]:
            print(
                f"  stm {row['entry_id'][:8]}… [{row['kind']}] "
                f"{_print_snip('s', row['snip'])}"
            )
        for row in exp_rows[:8]:
            print(
                f"  exp {row['experience_id'][:8]}… [{row['kind']}] "
                f"{_print_snip('s', row['snip'])}"
            )
        for row in ref_rows[:8]:
            print(
                f"  ref {row['reflection_id'][:8]}… "
                f"{_print_snip('s', row['snip'])}"
            )

        if args.dry_run:
            print("dry-run: no deletes")
            if not args.no_digest:
                path = digest_path()
                if path.is_file():
                    data = json.loads(path.read_text(encoding="utf-8"))
                    iv = data.get("inner_voice_summary") or ""
                    print(
                        "inner_voice literary:",
                        bool(iv) and is_literary_overnight_contaminated(iv),
                        f"len={len(iv)}",
                    )
            return 0

        if not stm_rows and not exp_rows and not ref_rows:
            print("nothing to delete in social.db")
            if not args.no_digest:
                print(rebuild_digest())
            return 0

        if not args.no_backup:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            backup = (
                Path.home()
                / ".claude"
                / "backups"
                / f"purge-literary-social-{ts}"
                / "social.db"
            )
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(db_path, backup)
            print(f"backup: {backup}")

        stats = purge(
            conn,
            stm_ids=[str(r["entry_id"]) for r in stm_rows],
            exp_ids=[str(r["experience_id"]) for r in exp_rows],
            reflection_ids=[str(r["reflection_id"]) for r in ref_rows],
        )
        print(f"deleted: {stats}")
        if not args.no_digest:
            print(rebuild_digest())
        print("NOTE: restart presence-ui so compose picks up cleaned social.db")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
