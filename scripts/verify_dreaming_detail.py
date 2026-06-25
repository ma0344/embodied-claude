"""One-off dreaming verification detail (ma-home)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def main() -> int:
    db = Path.home() / ".claude" / "sociality" / "social.db"
    if not db.is_file():
        db = Path.home() / ".claude" / "social.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    digest_path = Path.home() / ".claude" / "presence-ui" / "last_dream_digest.json"
    d = json.loads(digest_path.read_text(encoding="utf-8"))

    print("=== Last dream ===")
    dt = datetime.fromisoformat(d["dreamed_at"].replace("Z", "+00:00")).astimezone(
        ZoneInfo("Asia/Tokyo")
    )
    print(f"dreamed_at JST: {dt:%Y-%m-%d %H:%M:%S}")
    print(f"local_day: {d['local_day']}  daybook: {d.get('daybook_day')}")
    print(f"stm_batch: {len(d['stm_entry_ids'])} entries")
    print(f"remembered_count: {d['remembered_count']}")
    stats = d.get("consolidate_stats") or {}
    print(
        f"consolidate: ok={d['consolidate_ok']} "
        f"replay={stats.get('replay_events')} refreshed={stats.get('refreshed_memories')}"
    )

    summary = d.get("summary", "")
    inner = d.get("inner_voice_summary", "")
    print(f"gateway in digest: {'gateway_turn_context' in summary.lower()}")
    print(f"inner_voice present: {bool(inner and inner.strip())}")

    lines = summary.split("\n")
    echo_hits: list[str] = []
    for i, line in enumerate(lines):
        if line.startswith("こより: ") and i > 0:
            prev = lines[i - 1].strip()
            if prev.startswith("まー: ") and line[4:].strip() == prev[3:].strip():
                echo_hits.append(line[:80])
    print(f"echo lines in digest: {len(echo_hits)}")
    for e in echo_hits[:5]:
        print("  -", e)

    print("\n=== STM by local_day ===")
    for day in ("2026-06-20", "2026-06-21", "2026-06-22", "2026-06-23"):
        u = conn.execute(
            "SELECT COUNT(*) FROM stm_entries WHERE person_id=? AND local_day=? AND dreamed_at IS NULL",
            ("ma", day),
        ).fetchone()[0]
        dr = conn.execute(
            "SELECT COUNT(*) FROM stm_entries WHERE person_id=? AND local_day=? AND dreamed_at IS NOT NULL",
            ("ma", day),
        ).fetchone()[0]
        kinds = {
            r["kind"]: r["c"]
            for r in conn.execute(
                "SELECT kind, COUNT(*) c FROM stm_entries WHERE person_id=? AND local_day=? GROUP BY kind",
                ("ma", day),
            )
        }
        print(f"{day}: undreamed={u} dreamed={dr}  kinds={kinds}")

    print("\n=== episode_close (2026-06-22/23) ===")
    rows = conn.execute(
        """
        SELECT entry_id, summary, dreamed_at IS NOT NULL as dreamed FROM stm_entries
        WHERE person_id=? AND kind='episode_close' AND local_day IN ('2026-06-22','2026-06-23')
        ORDER BY created_at DESC LIMIT 6
        """,
        ("ma",),
    ).fetchall()
    for r in rows:
        s = r["summary"] or ""
        has_echo = False
        for i, line in enumerate(s.split("\n")):
            if line.startswith("こより: ") and i > 0:
                prev = s.split("\n")[i - 1].strip()
                if prev.startswith("まー: ") and line[4:].strip() == prev[3:].strip():
                    has_echo = True
        print(
            r["entry_id"],
            "dreamed" if r["dreamed"] else "pending",
            "echo=",
            has_echo,
            "gateway=",
            ("gateway_turn_context" in s.lower()),
        )
        preview = s.replace("\n", " | ")[:160]
        print(" ", preview)

    print("\n=== daybook ===")
    for table, col in (
        ("narrative_daybooks", "content"),
        ("daybook_entries", "body"),
        ("daybook_entries", "summary"),
    ):
        try:
            row = conn.execute(
                f"SELECT day, substr({col},1,500) FROM {table} WHERE day=? ORDER BY updated_at DESC LIMIT 1",
                (d["daybook_day"],),
            ).fetchone()
            if row:
                print(f"from {table}.{col}:")
                print(row[0], (row[1] or "")[:400])
                break
        except sqlite3.OperationalError:
            continue
    else:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        print("daybook table not found; related:", [t for t in tables if "day" in t or "narr" in t])

    print("\n=== dreamed batch (non-reflection) ===")
    ids = d["stm_entry_ids"]
    placeholders = ",".join("?" * len(ids))
    rows = conn.execute(
        f"""
        SELECT kind, substr(summary,1,120) s FROM stm_entries
        WHERE entry_id IN ({placeholders})
          AND kind != 'agent_private_reflection'
        ORDER BY kind, entry_id
        """,
        ids,
    ).fetchall()
    for r in rows:
        print(r["kind"], "|", (r["s"] or "").replace("\n", " ")[:110])

    print("\n=== multi-line echo in digest ===")
    in_digest = "まー: おるよ〜" in summary and "こより: おるよ〜" in summary
    print("inbound-style echo still visible:", in_digest)

    pulse = json.loads(
        (Path.home() / ".claude" / "presence-ui" / "agent_pulse.json").read_text(encoding="utf-8")
    )
    print("\n=== agent_pulse ===")
    print("last_dream_at:", pulse.get("last_dream_at"))
    print("last_consolidate_at:", pulse.get("last_consolidate_at"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
