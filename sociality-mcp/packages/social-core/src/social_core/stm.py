"""STM (short-term memory) store — MEM-1 daily buffer in social.db."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from .db import SocialDB
from .time import DEFAULT_POLICY_TIMEZONE, local_view, utc_now

StmSource = Literal[
    "wm_turn",
    "wm_flush",
    "experience_mirror",
    "episode_summary",
    "manual",
]

STM_AUTO_MIRROR_KINDS = frozenset(
    {
        "body_affliction",
        "agent_boundary",
        "open_loop_progress",
        "agent_private_reflection",
        "interpretation_shift",
    }
)
STM_AUTO_MIRROR_MIN_IMPORTANCE = 4


@dataclass(slots=True)
class StmEntry:
    entry_id: str
    ts: str
    local_day: str
    person_id: str | None
    source: str
    kind: str
    summary: str
    session_id: str | None
    experience_id: str | None
    turn_index: int | None
    importance: int
    dreamed_at: str | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "ts": self.ts,
            "local_day": self.local_day,
            "person_id": self.person_id,
            "source": self.source,
            "kind": self.kind,
            "summary": self.summary,
            "session_id": self.session_id,
            "experience_id": self.experience_id,
            "turn_index": self.turn_index,
            "importance": self.importance,
            "dreamed_at": self.dreamed_at,
            "created_at": self.created_at,
        }


def local_day_for_ts(ts: str, timezone: str = DEFAULT_POLICY_TIMEZONE) -> str:
    return local_view(ts, timezone).date().isoformat()


class StmStore:
    """Append-only short-term memory buffer (~24h / calendar day)."""

    def __init__(self, db: SocialDB) -> None:
        self.db = db

    def append(
        self,
        *,
        summary: str,
        kind: str,
        source: StmSource,
        ts: str | None = None,
        person_id: str | None = None,
        session_id: str | None = None,
        experience_id: str | None = None,
        turn_index: int | None = None,
        importance: int = 3,
        metadata: dict[str, Any] | None = None,
        timezone: str = DEFAULT_POLICY_TIMEZONE,
    ) -> StmEntry:
        text = summary.strip()
        if not text:
            raise ValueError("summary must not be empty")
        now = utc_now()
        entry_ts = ts or now
        entry_id = f"stm_{uuid.uuid4().hex[:12]}"
        local_day = local_day_for_ts(entry_ts, timezone)
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO stm_entries(
                    entry_id, ts, local_day, person_id, source, kind, summary,
                    session_id, experience_id, turn_index, metadata_json,
                    importance, dreamed_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
                """,
                (
                    entry_id,
                    entry_ts,
                    local_day,
                    person_id,
                    source,
                    kind,
                    text[:4000],
                    session_id,
                    experience_id,
                    turn_index,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    max(1, min(importance, 5)),
                    now,
                ),
            )
        return StmEntry(
            entry_id=entry_id,
            ts=entry_ts,
            local_day=local_day,
            person_id=person_id,
            source=source,
            kind=kind,
            summary=text[:4000],
            session_id=session_id,
            experience_id=experience_id,
            turn_index=turn_index,
            importance=max(1, min(importance, 5)),
            dreamed_at=None,
            created_at=now,
        )

    def flush_wm_turns(
        self,
        *,
        turns: list[dict[str, Any]],
        person_id: str | None = None,
        session_id: str | None = None,
        trigger: str = "manual",
        timezone: str = DEFAULT_POLICY_TIMEZONE,
    ) -> list[StmEntry]:
        """Persist chat turns from WM (session) into STM without per-turn LLM summary."""
        entries: list[StmEntry] = []
        for index, turn in enumerate(turns):
            sender = str(turn.get("sender") or "").strip().lower()
            message = str(turn.get("message") or "").strip()
            if not message or sender not in {"ma", "koyori"}:
                continue
            ts = str(turn.get("timestamp") or turn.get("ts") or utc_now())
            entries.append(
                self.append(
                    summary=message,
                    kind=f"wm_turn_{sender}",
                    source="wm_flush",
                    ts=ts,
                    person_id=person_id,
                    session_id=session_id,
                    turn_index=index,
                    importance=2,
                    metadata={"trigger": trigger, "sender": sender},
                    timezone=timezone,
                )
            )
        return entries

    def should_mirror_experience(self, *, kind: str, importance: int) -> bool:
        return kind in STM_AUTO_MIRROR_KINDS or importance >= STM_AUTO_MIRROR_MIN_IMPORTANCE

    def mirror_experience(
        self,
        experience_id: str,
        *,
        timezone: str = DEFAULT_POLICY_TIMEZONE,
    ) -> StmEntry | None:
        """Copy an agent_experience row into STM if eligible and not already mirrored."""
        row = self.db.fetchone(
            """
            SELECT experience_id, ts, person_id, kind, summary, importance
            FROM agent_experiences
            WHERE experience_id = ?
            """,
            (experience_id,),
        )
        if row is None:
            return None
        kind = str(row["kind"])
        importance = int(row["importance"])
        if not self.should_mirror_experience(kind=kind, importance=importance):
            return None
        existing = self.db.fetchone(
            "SELECT entry_id FROM stm_entries WHERE experience_id = ? LIMIT 1",
            (experience_id,),
        )
        if existing is not None:
            return None
        return self.append(
            summary=str(row["summary"]),
            kind=kind,
            source="experience_mirror",
            ts=str(row["ts"]),
            person_id=row["person_id"],
            experience_id=experience_id,
            importance=importance,
            timezone=timezone,
        )

    def recent(
        self,
        *,
        person_id: str | None = None,
        limit: int = 20,
        local_day: str | None = None,
        undreamed_only: bool = False,
    ) -> list[StmEntry]:
        where: list[str] = []
        args: list[Any] = []
        if person_id is not None:
            where.append("(person_id = ? OR person_id IS NULL)")
            args.append(person_id)
        if local_day:
            where.append("local_day = ?")
            args.append(local_day)
        if undreamed_only:
            where.append("dreamed_at IS NULL")
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        rows = self.db.fetchall(
            f"""
            SELECT entry_id, ts, local_day, person_id, source, kind, summary,
                   session_id, experience_id, turn_index, importance, dreamed_at, created_at
            FROM stm_entries
            {clause}
            ORDER BY ts DESC, created_at DESC
            LIMIT ?
            """,
            (*args, max(1, min(limit, 200))),
        )
        return [_row_to_entry(row) for row in rows]

    def count_for_day(self, *, local_day: str, person_id: str | None = None) -> int:
        if person_id is None:
            row = self.db.fetchone(
                "SELECT COUNT(*) FROM stm_entries WHERE local_day = ?",
                (local_day,),
            )
        else:
            row = self.db.fetchone(
                """
                SELECT COUNT(*) FROM stm_entries
                WHERE local_day = ? AND (person_id = ? OR person_id IS NULL)
                """,
                (local_day, person_id),
            )
        return int(row[0]) if row else 0

    def episode_closure_entry_id(self, session_id: str) -> str | None:
        row = self.db.fetchone(
            "SELECT stm_entry_id FROM session_episode_closures WHERE session_id = ?",
            (session_id,),
        )
        if row is None:
            return None
        return str(row["stm_entry_id"])

    def close_episode(
        self,
        *,
        summary: str,
        person_id: str | None = None,
        session_id: str | None = None,
        trigger: str = "new_session",
        turn_count: int = 0,
        ts: str | None = None,
        timezone: str = DEFAULT_POLICY_TIMEZONE,
    ) -> StmEntry | None:
        """Persist one episode summary into STM (idempotent per session_id)."""
        if not session_id:
            return None
        existing_id = self.episode_closure_entry_id(session_id)
        if existing_id:
            row = self.db.fetchone(
                """
                SELECT entry_id, ts, local_day, person_id, source, kind, summary,
                       session_id, experience_id, turn_index, importance, dreamed_at, created_at
                FROM stm_entries WHERE entry_id = ?
                """,
                (existing_id,),
            )
            return _row_to_entry(row) if row is not None else None

        text = summary.strip()
        if not text:
            return None

        entry = self.append(
            summary=text,
            kind="episode_close",
            source="episode_summary",
            ts=ts,
            person_id=person_id,
            session_id=session_id,
            importance=3,
            metadata={"trigger": trigger, "turn_count": turn_count},
            timezone=timezone,
        )
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO session_episode_closures(
                    session_id, stm_entry_id, person_id, trigger, turn_count, closed_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    entry.entry_id,
                    person_id,
                    trigger,
                    turn_count,
                    utc_now(),
                ),
            )
        return entry

    def mark_dreamed(self, entry_ids: list[str], *, dreamed_at: str | None = None) -> int:
        when = dreamed_at or utc_now()
        updated = 0
        with self.db.transaction() as conn:
            for entry_id in entry_ids:
                cursor = conn.execute(
                    """
                    UPDATE stm_entries
                    SET dreamed_at = ?
                    WHERE entry_id = ? AND dreamed_at IS NULL
                    """,
                    (when, entry_id),
                )
                updated += int(cursor.rowcount or 0)
        return updated

    def count_undreamed(self, *, person_id: str | None = None, local_day: str | None = None) -> int:
        where = ["dreamed_at IS NULL"]
        args: list[Any] = []
        if person_id is not None:
            where.append("(person_id = ? OR person_id IS NULL)")
            args.append(person_id)
        if local_day:
            where.append("local_day = ?")
            args.append(local_day)
        row = self.db.fetchone(
            f"SELECT COUNT(*) FROM stm_entries WHERE {' AND '.join(where)}",
            tuple(args),
        )
        return int(row[0]) if row else 0


def _row_to_entry(row: Any) -> StmEntry:
    return StmEntry(
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


def build_stm_prompt_block(entries: list[StmEntry], *, max_chars: int = 2000) -> str:
    """Compact block for compose injection (MEM-4 will expand usage)."""
    if not entries:
        return ""
    lines = ["[stm_recent]"]
    total = len("[stm_recent]\n[/stm_recent]")
    for entry in entries[:12]:
        line = f"- ({entry.kind}) {entry.summary[:200]}"
        if total + len(line) + 1 > max_chars:
            break
        lines.append(line)
        total += len(line) + 1
    lines.append("[/stm_recent]")
    return "\n".join(lines)
