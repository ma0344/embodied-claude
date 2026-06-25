#!/usr/bin/env python3
"""Debug compose path for ねっとわん いつ (Room vs verify)."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DB = os.path.expanduser("~/.claude/sociality/social.db")
COMPOSE = "http://127.0.0.1:8090/api/v1/heartbeat/compose-plan"


def main() -> None:
    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT profile_json FROM persons WHERE person_id='ma'"
    ).fetchone()
    conn.close()
    gists = json.loads(row[0] or "{}").get("self_disclosure_gists", [])
    print("=== profile gists ===")
    for item in gists:
        t = item.get("gist", "") if isinstance(item, dict) else str(item)
        print(
            f"  水曜={('水曜' in t)} 午前={('午前' in t)} "
            f"ねっとわん={('ねっとわん' in t or 'ネットワン' in t)}"
        )
        print(f"    {t[:120]}...")

    for lite in (False, True):
        body = json.dumps(
            {"person_id": "ma", "user_text": "ねっとわん いつ", "lite": lite}
        ).encode()
        req = urllib.request.Request(
            COMPOSE,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        r = json.loads(urllib.request.urlopen(req, timeout=30).read())
        ctx = r["ctx"]
        mems = ctx.get("relevant_memories") or []
        block = ctx.get("compact_prompt_block", "")
        print(f"\n=== compose lite={lite} mems={len(mems)} block={len(block)} ===")
        for i, m in enumerate(mems[:5]):
            c = m.get("content", "")
            print(
                f"  {i} r={m.get('relevance', 0):.2f} "
                f"水曜={'水曜' in c} 午前={'午前' in c} epis={'【会話' in c}"
            )
            print(f"     {c[:110].replace(chr(10), ' ')}...")
        idx = block.find("[relevant_memories]")
        if idx >= 0:
            print("\n--- [relevant_memories] block ---")
            print(block[idx : idx + 500])
        pg = block.find("[person_profile_gists]")
        if pg >= 0:
            print("\n--- [person_profile_gists] block ---")
            print(block[pg : pg + 300])


if __name__ == "__main__":
    main()
