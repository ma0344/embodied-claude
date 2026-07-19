"""STM (short-term memory) store — MEM-1 daily buffer in social.db."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from .db import SocialDB
from .stm_episode import sanitize_episode_summary_text
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
    metadata_json: str | None = None

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
            "metadata_json": self.metadata_json,
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
        from social_core.date_resolution import anchor_relative_dates_in_text

        anchored, _ = anchor_relative_dates_in_text(
            text, updated_at=entry_ts, tz_name=timezone
        )
        text = anchored
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
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
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

    def _open_loops_for_person(self, person_id: str | None) -> list[tuple[str, str]]:
        if not person_id:
            return []
        rows = self.db.fetchall(
            """
            SELECT loop_id, topic
            FROM open_loops
            WHERE person_id = ? AND status = 'open'
            ORDER BY updated_at DESC
            LIMIT 20
            """,
            (person_id,),
        )
        return [(str(row[0]), str(row[1])) for row in rows]

    def mirror_experience(
        self,
        experience_id: str,
        *,
        timezone: str = DEFAULT_POLICY_TIMEZONE,
    ) -> StmEntry | None:
        """Copy an agent_experience row into STM if eligible and not already mirrored."""
        row = self.db.fetchone(
            """
            SELECT experience_id, ts, person_id, kind, summary, importance,
                   desires_before_json, desires_after_json
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
        summary = str(row["summary"] or "")
        from social_core.literary_surface import is_literary_agent_surface

        # LW-READ dumps stay on experience/しおり — not conversational STM.
        if is_literary_agent_surface(summary):
            return None
        existing = self.db.fetchone(
            "SELECT entry_id FROM stm_entries WHERE experience_id = ? LIMIT 1",
            (experience_id,),
        )
        if existing is not None:
            return None
        from social_core.stm_salience import salience_from_experience_row

        person_id = row["person_id"]
        salience = salience_from_experience_row(
            row,
            open_loops=self._open_loops_for_person(person_id),
        )
        return self.append(
            summary=summary,
            kind=kind,
            source="experience_mirror",
            ts=str(row["ts"]),
            person_id=person_id,
            experience_id=experience_id,
            importance=importance,
            metadata=salience,
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
                   session_id, experience_id, turn_index, importance, dreamed_at, created_at,
                   metadata_json
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
        salience: dict[str, Any] | None = None,
    ) -> StmEntry | None:
        """Persist one episode summary into STM (idempotent per session_id)."""
        if not session_id:
            return None
        existing_id = self.episode_closure_entry_id(session_id)
        if existing_id:
            row = self.db.fetchone(
                """
                SELECT entry_id, ts, local_day, person_id, source, kind, summary,
                       session_id, experience_id, turn_index, importance, dreamed_at, created_at,
                       metadata_json
                FROM stm_entries WHERE entry_id = ?
                """,
                (existing_id,),
            )
            return _row_to_entry(row) if row is not None else None

        text = summary.strip()
        if not text:
            return None

        from social_core.stm_salience import build_stm_salience_metadata, match_open_loop_ids

        if salience is None:
            loops = self._open_loops_for_person(person_id)
            match_ids = match_open_loop_ids(text, loops)
            salience_meta = build_stm_salience_metadata(
                summary=text,
                kind="episode_close",
                source="episode_summary",
                importance=3,
                open_loop_ids=match_ids or None,
            )
        else:
            salience_meta = salience
        metadata = {"trigger": trigger, "turn_count": turn_count, **salience_meta}

        entry = self.append(
            summary=text,
            kind="episode_close",
            source="episode_summary",
            ts=ts,
            person_id=person_id,
            session_id=session_id,
            importance=int(salience_meta.get("importance") or 3),
            metadata=metadata,
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

    def update_summary(self, entry_id: str, summary: str) -> bool:
        text = (summary or "").strip()
        if not text:
            return False
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE stm_entries SET summary = ? WHERE entry_id = ?",
                (text, entry_id),
            )
            return int(cursor.rowcount or 0) > 0

    def repair_episode_close_summaries(self) -> tuple[int, int]:
        """Sanitize polluted episode_close rows (MEM-5g, inbound echo). Returns (scanned, updated)."""
        rows = self.db.fetchall(
            """
            SELECT entry_id, summary FROM stm_entries
            WHERE kind = 'episode_close'
              AND (
                summary LIKE '%gateway_turn_context%'
                OR summary LIKE '%まー:%こより:%'
              )
            """
        )
        updated = 0
        for row in rows:
            cleaned = sanitize_episode_summary_text(str(row["summary"]))
            if cleaned != row["summary"]:
                if self.update_summary(str(row["entry_id"]), cleaned):
                    updated += 1
        return len(rows), updated

    def get_entry(self, entry_id: str) -> StmEntry | None:
        row = self.db.fetchone(
            "SELECT * FROM stm_entries WHERE entry_id = ?",
            (entry_id,),
        )
        if row is None:
            return None
        return _row_to_entry(row)


def _summary_for_prompt(entry: StmEntry) -> str:
    if entry.kind == "episode_close":
        return sanitize_episode_summary_text(entry.summary)
    return entry.summary


# Surface chat already has room transcript (events + messages[]).
# episode_close dialogue dumps and tick templates only confuse [stm_recent].
_STM_SURFACE_SKIP_KINDS = frozenset({"episode_close"})
_STM_SURFACE_SKIP_MARKERS = (
    "Autonomous tick with a dominant desire",
    "Autonomous tick during inward hours",
    "Autonomous tick with no strong signal",
    "prefer a private note over any speech",
    "[interaction_context]",
    "[gateway_turn_context",
)


def should_skip_stm_surface_inject(*, kind: str, summary: str) -> bool:
    """True when an STM row should not appear in compose ``[stm_recent]``.

    DB encode / Dreaming still keep the row. Only the chat inject path skips.
    """
    if kind in _STM_SURFACE_SKIP_KINDS:
        return True
    from social_core.literary_surface import is_literary_agent_surface

    cleaned = (summary or "").strip()
    if not cleaned:
        return True
    if is_literary_agent_surface(cleaned):
        return True
    return any(marker in cleaned for marker in _STM_SURFACE_SKIP_MARKERS)


def _row_to_entry(row: Any) -> StmEntry:
    keys = row.keys() if hasattr(row, "keys") else []
    metadata = row["metadata_json"] if "metadata_json" in keys else None
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
        metadata_json=metadata,
    )


def build_stm_prompt_block(entries: list[StmEntry], *, max_chars: int = 2000) -> str:
    """Compact block for compose injection (MEM-4 will expand usage)."""
    if not entries:
        return ""
    lines = ["[stm_recent]"]
    total = len("[stm_recent]\n[/stm_recent]")
    seen_summaries: set[str] = set()
    # Scan beyond 12 so skips (episode_close / tick templates) do not empty the block.
    for entry in entries[:24]:
        if should_skip_stm_surface_inject(kind=entry.kind, summary=entry.summary):
            continue
        summary = (_summary_for_prompt(entry) or "").strip()
        if not summary:
            continue
        dedupe_key = " ".join(summary.split())[:160]
        if dedupe_key in seen_summaries:
            continue
        seen_summaries.add(dedupe_key)
        line = f"- ({entry.kind}) {summary[:200]}"
        if total + len(line) + 1 > max_chars:
            break
        lines.append(line)
        total += len(line) + 1
        if len(lines) >= 14:  # header + up to 12 bullets
            break
    lines.append("[/stm_recent]")
    if len(lines) <= 2:
        return ""
    return "\n".join(lines)
