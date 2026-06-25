#!/usr/bin/env python3
"""Quick MEM-8e / MEM-8 recall state check (ma-home)."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import urllib.parse
import urllib.request

RECALL_BASE = "http://127.0.0.1:18900/recall"


def recall_top(query: str, n: int = 1) -> str:
    q = urllib.parse.quote(query)
    with urllib.request.urlopen(f"{RECALL_BASE}?q={q}&n={n}", timeout=10) as resp:
        rows = json.loads(resp.read())
    if not rows:
        return "(empty)"
    return str(rows[0].get("content", ""))[:140]


def main() -> int:
    print("=== MEM-8e / recall state ===\n")

    queries = ["ここっち", "ここっち グループホーム", "ネットワン 水曜"]
    for q in queries:
        top = recall_top(q)
        kind = "FACT" if "グループホーム" in top or "ここっち" in top and "embodied-claude" in top else "OTHER"
        if "【会話の区切り】" in top or "episode" in top.lower():
            kind = "EPISODE"
        print(f"recall({q!r}) -> [{kind}]")
        print(f"  {top}\n")

    db = os.path.expanduser("~/.claude/sociality/social.db")
    print(f"social.db: {db} exists={os.path.exists(db)}")
    if os.path.exists(db):
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT person_id, profile_json FROM persons WHERE person_id='ma'"
            ).fetchone()
            if row:
                profile = json.loads(row["profile_json"] or "{}")
                gists = profile.get("self_disclosure_gists", [])
                print(f"  ma profile gists ({len(gists)}):")
                for item in gists[:5]:
                    if isinstance(item, dict):
                        print(f"    - {item.get('gist', '')!r}")
            else:
                print("  ma: not in persons table")
        except sqlite3.Error as exc:
            print(f"  persons query error: {exc}")
        try:
            stm = conn.execute(
                """
                SELECT entry_id, kind, substr(summary, 1, 100) AS snippet
                FROM stm_entries
                WHERE person_id='ma' AND kind='self_disclosure'
                ORDER BY rowid DESC LIMIT 3
                """
            ).fetchall()
            print(f"  STM self_disclosure rows: {len(stm)}")
            for r in stm:
                print(f"    entry_id={r['entry_id']} {r['snippet']!r}")
        except sqlite3.Error as exc:
            print(f"  stm query error: {exc}")
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
