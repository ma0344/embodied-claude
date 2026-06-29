"""Persistence layer for agent experiences, reflections, and interpretation shifts."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from social_core import SocialDB, utc_now

from .schemas import (
    AppendPrivateReflectionInput,
    ComposePrivateLetterInput,
    InterpretationShiftSummary,
    RecentExperienceRef,
    RecordAgentExperienceInput,
    RecordInterpretationShiftInput,
)


@dataclass(slots=True)
class StoredExperience:
    experience_id: str
    ts: str


def _bool_to_int(value: bool) -> int:
    return 1 if value else 0


class InteractionOrchestratorStore:
    """Writes interaction metadata into the shared sociality SQLite database."""

    def __init__(self, path: str | Path | None = None, db: SocialDB | None = None) -> None:
        self.db = db or SocialDB(path)

    def close(self) -> None:
        self.db.close()

    # ------------------------------------------------------------------
    # agent experiences
    # ------------------------------------------------------------------

    def record_agent_experience(self, payload: RecordAgentExperienceInput) -> StoredExperience:
        experience_id = f"exp_{uuid.uuid4().hex[:12]}"
        ts = payload.ts or utc_now()
        from social_core.date_resolution import anchor_relative_dates_in_text

        summary, _ = anchor_relative_dates_in_text(
            payload.summary, updated_at=ts, tz_name="Asia/Tokyo"
        )
        private_summary = payload.private_summary
        if private_summary:
            private_summary, _ = anchor_relative_dates_in_text(
                private_summary, updated_at=ts, tz_name="Asia/Tokyo"
            )
        public_summary = payload.public_summary
        if public_summary:
            public_summary, _ = anchor_relative_dates_in_text(
                public_summary, updated_at=ts, tz_name="Asia/Tokyo"
            )
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO agent_experiences(
                    experience_id, ts, person_id, kind, summary,
                    private_summary, public_summary, why,
                    felt_state_json, desires_before_json, desires_after_json,
                    related_event_ids, related_memory_ids, artifacts_json,
                    importance, privacy_level, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experience_id,
                    ts,
                    payload.person_id,
                    payload.kind,
                    summary,
                    private_summary,
                    public_summary,
                    payload.why,
                    json.dumps(payload.felt_state or {}, ensure_ascii=False, sort_keys=True),
                    json.dumps(payload.desires_before or {}, ensure_ascii=False, sort_keys=True),
                    json.dumps(payload.desires_after or {}, ensure_ascii=False, sort_keys=True),
                    ",".join(payload.related_event_ids),
                    ",".join(payload.related_memory_ids),
                    json.dumps(payload.artifacts, ensure_ascii=False),
                    payload.importance,
                    payload.privacy_level,
                    utc_now(),
                ),
            )
        self._mirror_to_stm(experience_id)
        return StoredExperience(experience_id=experience_id, ts=ts)

    def _mirror_to_stm(self, experience_id: str) -> None:
        from social_core.stm import StmStore

        try:
            StmStore(self.db).mirror_experience(experience_id)
        except Exception:
            pass

    def recent_agent_experiences(
        self,
        *,
        person_id: str | None = None,
        limit: int = 5,
        include_private: bool = True,
    ) -> list[RecentExperienceRef]:
        where: list[str] = []
        args: list[Any] = []
        if person_id is not None:
            where.append("person_id = ?")
            args.append(person_id)
        if not include_private:
            where.append("privacy_level != 'private'")
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        rows = self.db.fetchall(
            f"""
            SELECT experience_id, ts, kind, summary, importance
            FROM agent_experiences
            {clause}
            ORDER BY ts DESC, created_at DESC
            LIMIT ?
            """,
            (*args, max(1, min(limit, 50))),
        )
        return [
            RecentExperienceRef(
                experience_id=row[0],
                ts=row[1],
                kind=row[2],
                summary=row[3],
                importance=int(row[4]),
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # private reflections and letters
    # ------------------------------------------------------------------

    def append_private_reflection(
        self, payload: AppendPrivateReflectionInput
    ) -> StoredExperience:
        reflection_id = f"ref_{uuid.uuid4().hex[:12]}"
        ts = utc_now()
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO private_reflections(
                    reflection_id, ts, person_id, title, body, tags,
                    importance, may_surface_later, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reflection_id,
                    ts,
                    payload.person_id,
                    payload.title,
                    payload.body,
                    ",".join(payload.tags),
                    payload.importance,
                    _bool_to_int(payload.may_surface_later),
                    ts,
                ),
            )
        return StoredExperience(experience_id=reflection_id, ts=ts)

    def count_private_reflections(self, *, person_id: str | None = None) -> int:
        if person_id is None:
            row = self.db.fetchone("SELECT COUNT(*) FROM private_reflections")
        else:
            row = self.db.fetchone(
                "SELECT COUNT(*) FROM private_reflections WHERE person_id = ?",
                (person_id,),
            )
        return int(row[0]) if row else 0

    def compose_private_letter(
        self, payload: ComposePrivateLetterInput
    ) -> StoredExperience:
        letter_id = f"ltr_{uuid.uuid4().hex[:12]}"
        ts = utc_now()
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO private_letters(
                    letter_id, ts, person_id, title, body,
                    intended_time, visibility, related_open_loops, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    letter_id,
                    ts,
                    payload.person_id,
                    payload.title,
                    payload.body,
                    payload.intended_time,
                    payload.visibility,
                    ",".join(payload.related_open_loops),
                    ts,
                ),
            )
        return StoredExperience(experience_id=letter_id, ts=ts)

    # ------------------------------------------------------------------
    # interpretation shifts
    # ------------------------------------------------------------------

    def record_interpretation_shift(
        self, payload: RecordInterpretationShiftInput
    ) -> StoredExperience:
        shift_id = f"shft_{uuid.uuid4().hex[:12]}"
        ts = payload.ts or utc_now()
        from social_core.date_resolution import DEFAULT_TIMEZONE, anchor_relative_dates_in_text

        tz_name = DEFAULT_TIMEZONE
        old_interpretation, _ = anchor_relative_dates_in_text(
            payload.old_interpretation, updated_at=ts, tz_name=tz_name
        )
        new_interpretation, resolved = anchor_relative_dates_in_text(
            payload.new_interpretation, updated_at=ts, tz_name=tz_name
        )
        resolved_date = resolved.isoformat() if resolved else None
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO interpretation_shifts(
                    shift_id, ts, person_id, topic,
                    old_interpretation, new_interpretation, trigger,
                    confidence, implications_json, created_at, resolved_date, domain
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    shift_id,
                    ts,
                    payload.person_id,
                    payload.topic,
                    old_interpretation,
                    new_interpretation,
                    payload.trigger,
                    payload.confidence,
                    json.dumps(payload.implications, ensure_ascii=False),
                    ts,
                    resolved_date,
                    payload.domain,
                ),
            )
        return StoredExperience(experience_id=shift_id, ts=ts)

    def count_interpretation_shifts(self) -> int:
        row = self.db.fetchone("SELECT COUNT(*) FROM interpretation_shifts")
        return int(row[0]) if row else 0

    def recent_interpretation_shifts(
        self,
        *,
        person_id: str | None = None,
        limit: int = 3,
    ) -> list[InterpretationShiftSummary]:
        where: list[str] = []
        args: list[Any] = []
        if person_id is not None:
            where.append("(person_id = ? OR person_id IS NULL)")
            args.append(person_id)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        rows = self.db.fetchall(
            f"""
            SELECT shift_id, ts, topic, old_interpretation, new_interpretation,
                   trigger, confidence, resolved_date, domain
            FROM interpretation_shifts
            {clause}
            ORDER BY ts DESC, created_at DESC
            LIMIT ?
            """,
            (*args, max(1, min(limit, 10))),
        )
        return [
            InterpretationShiftSummary(
                shift_id=row[0],
                ts=row[1],
                topic=row[2],
                old_interpretation=row[3],
                new_interpretation=row[4],
                trigger=row[5],
                confidence=float(row[6]),
                resolved_date=row[7],
                domain=row[8],
            )
            for row in rows
        ]
