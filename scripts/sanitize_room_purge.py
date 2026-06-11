#!/usr/bin/env python3
"""Sanitization purge for Koyori's Room after session-mixing incident."""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

TODAY_PREFIX = "2026-06-10"
CURSOR_SESSION = "room_d355489c0a93"
SCARY_TERMS = (
    "fear",
    "scary",
    "distort",
    "distorted",
    "scary persona",
    "怖い",
    "恐怖",
    "歪んだ",
    "歪み",
    "そのモデル",
    "心配するな",
    "別セッション",
    "心配して",
)


def backup_files(home: Path, backup_dir: Path) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    for rel in (
        "sociality/social.db",
        "presence-ui/sessions.json",
        "memories/memory.db",
    ):
        src = home / ".claude" / rel
        if src.is_file():
            dst = backup_dir / Path(rel).name
            shutil.copy2(src, dst)
            print(f"backed up {src} -> {dst}")


def purge_social_db(db_path: Path) -> dict[str, int]:
    stats: dict[str, int] = {}
    conn = sqlite3.connect(db_path)
    try:
        # 1) Remove entire Cursor-import room (unwanted copy)
        cur = conn.execute(
            "DELETE FROM events WHERE source = 'presence-ui' AND session_id = ?",
            (CURSOR_SESSION,),
        )
        stats["events_cursor_session"] = cur.rowcount

        # 2) Remove today's polluted presence-ui events in Claude Code import room
        cur = conn.execute(
            """
            DELETE FROM events
            WHERE source = 'presence-ui'
              AND session_id = 'room_8f589b33ae55'
              AND ts LIKE ?
            """,
            (TODAY_PREFIX + "%",),
        )
        stats["events_today_room_8f589"] = cur.rowcount

        # 3) Remove legacy room (session_id NULL) presence-ui events from today
        cur = conn.execute(
            """
            DELETE FROM events
            WHERE source = 'presence-ui'
              AND session_id IS NULL
              AND ts LIKE ?
            """,
            (TODAY_PREFIX + "%",),
        )
        stats["events_legacy_today"] = cur.rowcount

        # 4) Remove duplicate global chat-source events from today (session mixing)
        cur = conn.execute(
            """
            DELETE FROM events
            WHERE source = 'chat'
              AND ts LIKE ?
            """,
            (TODAY_PREFIX + "%",),
        )
        stats["events_chat_today"] = cur.rowcount

        # 5) Agent experiences from today (distorted persona responses)
        cur = conn.execute(
            "DELETE FROM agent_experiences WHERE ts LIKE ?",
            (TODAY_PREFIX + "%",),
        )
        stats["agent_experiences_today"] = cur.rowcount

        # 6) Open loops created/updated today from polluted chat
        cur = conn.execute(
            "DELETE FROM open_loops WHERE person_id = 'ma' AND updated_at LIKE ?",
            (TODAY_PREFIX + "%",),
        )
        stats["open_loops_ma_today"] = cur.rowcount

        # 7) Relationship snapshots from today (recomputed from polluted chat)
        cur = conn.execute(
            "DELETE FROM relationship_snapshots WHERE person_id = 'ma' AND ts LIKE ?",
            (TODAY_PREFIX + "%",),
        )
        stats["relationship_snapshots_ma_today"] = cur.rowcount

        # 8) Interpretation shifts from today (none expected, but safe)
        cur = conn.execute(
            "DELETE FROM interpretation_shifts WHERE ts LIKE ?",
            (TODAY_PREFIX + "%",),
        )
        stats["interpretation_shifts_today"] = cur.rowcount

        # 9) Private reflections from today if any scary content
        cur = conn.execute(
            f"""
            DELETE FROM private_reflections
            WHERE ts LIKE ?
              AND ({' OR '.join('body LIKE ?' for _ in SCARY_TERMS)})
            """,
            (TODAY_PREFIX + "%",) + tuple(f"%{t}%" for t in SCARY_TERMS),
        )
        stats["private_reflections_scary"] = cur.rowcount

        conn.commit()
    finally:
        conn.close()
    return stats


def purge_sessions_json(sessions_path: Path) -> list[str]:
    removed: list[str] = []
    if not sessions_path.is_file():
        return removed
    data = json.loads(sessions_path.read_text(encoding="utf-8"))
    sessions = data.get("sessions", {})
    if CURSOR_SESSION in sessions:
        del sessions[CURSOR_SESSION]
        removed.append(CURSOR_SESSION)
    data["sessions"] = sessions
    sessions_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return removed


def purge_memories(mem_db: Path) -> dict[str, int]:
    stats = {"memories_scary_recent": 0, "memories_today_all": 0}
    if not mem_db.is_file():
        return stats
    conn = sqlite3.connect(mem_db)
    try:
        # Delete memories from last 72h matching scary keywords
        where = " OR ".join("content LIKE ?" for _ in SCARY_TERMS)
        params = tuple(f"%{t}%" for t in SCARY_TERMS)
        ids = [
            row[0]
            for row in conn.execute(
                f"""
                SELECT id FROM memories
                WHERE timestamp >= datetime('now', '-72 hours')
                  AND ({where})
                """,
                params,
            )
        ]
        for memory_id in ids:
            conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        stats["memories_scary_recent"] = len(ids)

        # Also remove any memories created today that mention session mixing / distorted model
        extra_terms = ("session-mixing", "session mixing", "presence-ui", "sanitization")
        where2 = " OR ".join("content LIKE ?" for _ in extra_terms)
        params2 = (TODAY_PREFIX + "%",) + tuple(f"%{t}%" for t in extra_terms)
        cur = conn.execute(
            f"""
            DELETE FROM memories
            WHERE timestamp LIKE ?
              AND ({where2})
            """,
            params2,
        )
        stats["memories_today_polluted"] = cur.rowcount

        conn.commit()
    finally:
        conn.close()
    return stats


def verify(home: Path) -> None:
    db_path = home / ".claude" / "sociality" / "social.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    print("\n=== POST-PURGE: presence-ui sessions ===")
    for row in conn.execute(
        """
        SELECT session_id, COUNT(*) cnt, MAX(ts) last_ts
        FROM events WHERE source = 'presence-ui'
        GROUP BY session_id ORDER BY last_ts DESC
        """
    ):
        print(dict(row))
    print("\n=== POST-PURGE: today events remaining ===")
    row = conn.execute(
        "SELECT COUNT(*) FROM events WHERE ts LIKE ?",
        (TODAY_PREFIX + "%",),
    ).fetchone()
    print("today_events_remaining", row[0])
    print("\n=== POST-PURGE: interpretation_shifts ===")
    row = conn.execute("SELECT COUNT(*) FROM interpretation_shifts").fetchone()
    print("count", row[0])
    print("\n=== POST-PURGE: person ma ===")
    for row in conn.execute("SELECT person_id, profile_json FROM persons WHERE person_id='ma'"):
        print(dict(row))
    for row in conn.execute(
        "SELECT COUNT(*) FROM person_boundaries WHERE person_id='ma'"
    ):
        print("boundaries", row[0])
    conn.close()


def main() -> None:
    home = Path.home()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_dir = home / ".claude" / "backups" / f"sanitize-{ts}"

    print("=== Koyori Room Sanitization Purge ===")
    backup_files(home, backup_dir)

    social_stats = purge_social_db(home / ".claude" / "sociality" / "social.db")
    removed_sessions = purge_sessions_json(home / ".claude" / "presence-ui" / "sessions.json")
    mem_stats = purge_memories(home / ".claude" / "memories" / "memory.db")

    print("\n=== PURGE STATS ===")
    print("social_db:", json.dumps(social_stats, indent=2))
    print("removed_sessions:", removed_sessions)
    print("memory_db:", json.dumps(mem_stats, indent=2))
    print("backup_dir:", backup_dir)
    print("\nNOTE: working_memory is in-memory; restart memory-mcp to clear it.")

    verify(home)


if __name__ == "__main__":
    main()
