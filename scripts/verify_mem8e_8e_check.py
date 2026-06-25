#!/usr/bin/env python3
"""MEM-8e automated verification checklist (no Room required)."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import urllib.parse
import urllib.request

RECALL = "http://127.0.0.1:18900/recall"
COMPOSE = "http://127.0.0.1:8090/api/v1/heartbeat/compose-plan"
DB = os.path.expanduser("~/.claude/sociality/social.db")

DISAMBIG_MARKERS = ("ここっち", "グループホーム", "embodied-claude", "こっち")


def recall_rows(query: str, n: int = 3) -> list[dict]:
    q = urllib.parse.quote(query)
    with urllib.request.urlopen(f"{RECALL}?q={q}&n={n}", timeout=15) as resp:
        data = json.loads(resp.read())
    return data if isinstance(data, list) else []


def classify_ltm(content: str) -> str:
    if all(m in content for m in DISAMBIG_MARKERS[:3]) and "別" in content:
        return "FACT_DISAMBIG"
    if "【会話の区切り】" in content:
        return "EPISODE"
    return "OTHER"


def load_ma_gists() -> list[str]:
    if not os.path.exists(DB):
        return []
    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT profile_json FROM persons WHERE person_id='ma'"
    ).fetchone()
    conn.close()
    if not row:
        return []
    profile = json.loads(row[0] or "{}")
    out: list[str] = []
    for item in profile.get("self_disclosure_gists", []):
        if isinstance(item, dict):
            g = str(item.get("gist") or "").strip()
            if g:
                out.append(g)
    return out


def gist_has_disambig(gist: str) -> bool:
    return (
        "ここっち" in gist
        and "グループホーム" in gist
        and ("別" in gist or "embodied-claude" in gist or "こっち" in gist)
    )


def ltm_top_has_disambig(query: str) -> bool:
    rows = recall_rows(query, 1)
    if not rows:
        return False
    content = str(rows[0].get("content") or "")
    return classify_ltm(content) == "FACT_DISAMBIG"


def compose_injects_gists() -> tuple[bool, list[str]]:
    body = json.dumps({"person_id": "ma", "user_text": "ここっちの仕事の話"}).encode()
    req = urllib.request.Request(
        COMPOSE,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read())
    ctx = payload.get("ctx") or {}
    block = str(ctx.get("compact_prompt_block") or "")
    gists = list((ctx.get("person_model") or {}).get("profile_gists") or [])
    ok = "[person_profile_gists]" in block and any(gist_has_disambig(g) for g in gists)
    return ok, gists


def stm_self_disclosure_count() -> int:
    if not os.path.exists(DB):
        return 0
    conn = sqlite3.connect(DB)
    n = conn.execute(
        "SELECT COUNT(*) FROM stm_entries WHERE person_id='ma' AND kind='self_disclosure'"
    ).fetchone()[0]
    conn.close()
    return int(n)


def is_episode_content(content: str) -> bool:
    text = (content or "").strip()
    return "【会話の区切り】" in text or "【会話の一区切り】" in text or (
        len(text) > 360 and text.count("\n") >= 2
    )


def compose_relevant_memories(user_text: str) -> list[str]:
    body = json.dumps({"person_id": "ma", "user_text": user_text}).encode()
    req = urllib.request.Request(
        COMPOSE,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read())
    ctx = payload.get("ctx") or {}
    return [
        str(m.get("content") or "")
        for m in (ctx.get("relevant_memories") or [])
        if isinstance(m, dict)
    ]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    gists = load_ma_gists()
    disambig_gists = [g for g in gists if gist_has_disambig(g)]
    stm_n = stm_self_disclosure_count()
    compose_ok, compose_gists = compose_injects_gists()
    schedule_memories = compose_relevant_memories("ねっとわん いつ")

    checks: list[tuple[str, bool, str]] = [
        (
            "social.db 存在 + ma あり",
            os.path.exists(DB) and bool(gists),
            f"gists={len(gists)}",
        ),
        (
            "profile_gists: ここっち≠こっち disambig",
            bool(disambig_gists),
            disambig_gists[0][:80] + "..." if disambig_gists else "missing",
        ),
        (
            "LTM recall('ここっち') top=disambig fact",
            ltm_top_has_disambig("ここっち"),
            "top hit has GH name + embodied-claude distinction",
        ),
        (
            "LTM recall('ここっち グループホーム') top=disambig",
            ltm_top_has_disambig("ここっち グループホーム"),
            "same fact row expected",
        ),
        (
            "compose [person_profile_gists] 注入",
            compose_ok,
            f"injected {len(compose_gists)} gist(s)",
        ),
        (
            "compose recall('ねっとわん いつ') — MEM-8b top fact",
            bool(schedule_memories)
            and not is_episode_content(schedule_memories[0])
            and ("水曜" in schedule_memories[0] or "午前" in schedule_memories[0]),
            f"memories={len(schedule_memories)} top={(schedule_memories[0][:60]+'...') if schedule_memories else 'none'}",
        ),
        (
            "STM self_disclosure ≥1",
            stm_n >= 1,
            f"rows={stm_n}",
        ),
        (
            "LTM recall('ネットワン 水曜') — known MEM-8 gap",
            not ltm_top_has_disambig("ネットワン 水曜"),
            "episode/other expected until 8b/8a (informational)",
        ),
    ]

    print("MEM-8e automated verification\n")
    print("| Check | Result | Detail |")
    print("|-------|--------|--------|")
    fails = 0
    for name, ok, detail in checks:
        if name.startswith("LTM recall('ネットワン"):
            status = "INFO" if ok else "WARN"
        else:
            status = "PASS" if ok else "FAIL"
            if not ok:
                fails += 1
        detail_esc = detail.replace("|", "\\|")
        print(f"| {name} | {status} | {detail_esc} |")

    core_pass = fails == 0
    print()
    if core_pass:
        print("Overall: PASS (automated 8e checks)")
        print("8b: OK to proceed — L0 path works; schedule recall gap is 8b/8a scope")
        print("Room live: still manual (correction encode on new utterance)")
    else:
        print(f"Overall: FAIL ({fails} check(s))")
        print("8b: fix 8e gaps first or seed LTM/profile_gists manually")
    return 0 if core_pass else 1


if __name__ == "__main__":
    sys.exit(main())
