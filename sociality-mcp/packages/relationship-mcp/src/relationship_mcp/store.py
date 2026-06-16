"""Persistence helpers for relationship-mcp."""

from __future__ import annotations

import json
import re
import uuid
from datetime import timedelta
from pathlib import Path

from social_core import (
    EventStore,
    SocialDB,
    SocialEventCreate,
    ensure_iso8601,
    parse_timestamp,
)

from .date_resolution import DEFAULT_TIMEZONE, as_of_date, is_stale, resolve_relative_date
from .inference import (
    FUTURE_MARKERS,
    STRESS_KEYWORDS,
    compute_snapshot_metrics,
    extract_dismiss_topic,
    is_dismiss_utterance,
    is_recall_loop_topic,
    is_recall_utterance,
    suggest_followup_text,
    summarize_relationship,
)
from .reminder_intent import extract_reminder_request
from .schemas import (
    CommitmentRecord,
    DismissOutcome,
    OpenLoopRecord,
    PersonModel,
    PreferenceRecord,
    RitualRecord,
    SuggestionRecord,
)


class RelationshipStore:
    """Compact relationship storage built on the shared social DB."""

    def __init__(self, path: str | Path | None = None, db: SocialDB | None = None) -> None:
        self.db = db or SocialDB(path)
        self.events = EventStore(self.db)

    def close(self) -> None:
        self.db.close()

    def upsert_person(
        self,
        *,
        person_id: str,
        canonical_name: str,
        aliases: list[str] | None = None,
        role: str | None = None,
    ) -> dict[str, str]:
        aliases = aliases or []
        now = ensure_iso8601(self.events.get_latest_timestamp() or "2026-01-01T12:00:00+00:00")
        with self.db.transaction() as connection:
            connection.execute(
                """
                INSERT INTO persons(
                    person_id,
                    canonical_name,
                    role,
                    profile_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, '{}', ?, ?)
                ON CONFLICT(person_id) DO UPDATE SET
                    canonical_name = excluded.canonical_name,
                    role = excluded.role,
                    updated_at = excluded.updated_at
                """,
                (person_id, canonical_name, role, now, now),
            )
            connection.execute("DELETE FROM person_aliases WHERE person_id = ?", (person_id,))
            for alias in dict.fromkeys([canonical_name, *aliases]):
                connection.execute(
                    """
                    INSERT OR REPLACE INTO person_aliases(alias_id, person_id, alias)
                    VALUES (?, ?, ?)
                    """,
                    (f"alias_{uuid.uuid4().hex[:12]}", person_id, alias),
                )
        return {"person_id": person_id}

    def resolve_person_id(self, name_or_id: str) -> str | None:
        row = self.db.fetchone("SELECT person_id FROM persons WHERE person_id = ?", (name_or_id,))
        if row is not None:
            return str(row["person_id"])
        row = self.db.fetchone(
            "SELECT person_id FROM person_aliases WHERE alias = ?", (name_or_id,)
        )
        return None if row is None else str(row["person_id"])

    def ingest_interaction(
        self,
        *,
        person_id: str,
        channel: str,
        direction: str,
        text: str,
        ts: str,
    ) -> dict[str, str]:
        self._ensure_person(person_id)
        kind = "human_utterance" if direction == "human_to_ai" else "agent_utterance"
        event = self.events.ingest(
            SocialEventCreate(
                ts=ts,
                source=channel,
                kind=kind,
                person_id=person_id,
                confidence=0.92,
                payload={"text": text, "direction": direction},
            )
        )
        if direction == "human_to_ai":
            self.dismiss_from_utterance(
                person_id=person_id,
                text=text,
                ts=ts,
                source_event_id=event.event_id,
            )
            if not is_dismiss_utterance(text):
                self._update_open_loops(
                    person_id=person_id,
                    text=text,
                    source_event_id=event.event_id,
                    ts=ts,
                    direction=direction,
                )
                self.close_stale_open_loops(person_id=person_id, as_of=ts)
                self._maybe_create_reminder_commitment(
                    person_id=person_id,
                    text=text,
                    ts=ts,
                )
        else:
            self._update_open_loops(
                person_id=person_id,
                text=text,
                source_event_id=event.event_id,
                ts=ts,
                direction=direction,
            )
        self.refresh_snapshot(person_id)
        return {"event_id": event.event_id}

    def close_stale_open_loops(
        self,
        *,
        person_id: str,
        as_of: str,
        timezone: str = DEFAULT_TIMEZONE,
        include_today: bool = False,
    ) -> list[str]:
        """Close open loops whose relative-date topic is past due."""
        as_of_day = as_of_date(as_of_ts=as_of, tz_name=timezone)
        rows = self.db.fetchall(
            """
            SELECT loop_id, topic, updated_at
            FROM open_loops
            WHERE person_id = ? AND status = 'open'
            ORDER BY updated_at DESC
            """,
            (person_id,),
        )
        closed_topics: list[str] = []
        for loop_id, topic, updated_at in rows:
            passed = is_stale(
                topic=str(topic),
                updated_at=str(updated_at),
                tz_name=timezone,
                as_of=as_of_day,
                include_today=include_today,
            )
            if passed is None:
                continue
            detail = {
                "kind": "stale",
                "reason": "relative_date_passed",
                "resolved_date": passed.isoformat(),
                "source_topic": str(topic)[:200],
            }
            with self.db.transaction() as connection:
                connection.execute(
                    """
                    UPDATE open_loops
                    SET status = 'closed', updated_at = ?, detail_json = ?
                    WHERE loop_id = ?
                    """,
                    (as_of, json.dumps(detail, ensure_ascii=False), loop_id),
                )
            closed_topics.append(str(topic))
        return closed_topics

    def note_human_utterance_for_loops(
        self,
        *,
        person_id: str,
        text: str,
        ts: str,
        source_event_id: str,
    ) -> DismissOutcome:
        """Update or close/cancel relationship threads from a human room utterance."""

        self._ensure_person(person_id)
        outcome = self.dismiss_from_utterance(
            person_id=person_id,
            text=text,
            ts=ts,
            source_event_id=source_event_id,
        )
        outcome = outcome.model_copy(
            update={
                "closed_loops": [
                    *outcome.closed_loops,
                    *self._close_recall_noise_loops(
                        person_id=person_id,
                        ts=ts,
                        source_event_id=source_event_id,
                        source_text=text,
                    ),
                ]
            }
        )
        if is_dismiss_utterance(text) or is_recall_utterance(text):
            return outcome
        self._update_open_loops(
            person_id=person_id,
            text=text,
            source_event_id=source_event_id,
            ts=ts,
            direction="human_to_ai",
        )
        self.close_stale_open_loops(person_id=person_id, as_of=ts)
        self._maybe_create_reminder_commitment(
            person_id=person_id,
            text=text,
            ts=ts,
        )
        return outcome

    def dismiss_from_utterance(
        self,
        *,
        person_id: str,
        text: str,
        ts: str,
        source_event_id: str,
    ) -> DismissOutcome:
        """Close matching open loops and cancel active commitments on dismiss."""
        if not is_dismiss_utterance(text):
            return DismissOutcome()

        explicit_topic = extract_dismiss_topic(text)
        closed_loops: list[str] = []
        for loop in self.list_open_loops(person_id=person_id, limit=20):
            if not self._matches_dismiss_target(loop.topic, text, explicit_topic):
                continue
            self._close_open_loop(
                loop_id=loop.id,
                person_id=person_id,
                topic=loop.topic,
                ts=ts,
                source_event_id=source_event_id,
                source_text=text,
            )
            closed_loops.append(loop.topic)

        cancelled_commitments: list[str] = []
        for commitment in self.list_active_commitments(person_id=person_id, limit=20):
            if not self._matches_dismiss_target(commitment.text, text, explicit_topic):
                continue
            self._cancel_commitment(
                commitment_id=commitment.id,
                ts=ts,
                source_text=text,
            )
            cancelled_commitments.append(_commitment_label(commitment.text))

        return DismissOutcome(
            closed_loops=closed_loops,
            cancelled_commitments=cancelled_commitments,
        )

    def _close_recall_noise_loops(
        self,
        *,
        person_id: str,
        ts: str,
        source_event_id: str,
        source_text: str,
    ) -> list[str]:
        """Close stale recall-shaped loops (e.g. '煎餅の話、覚えてる')."""
        closed: list[str] = []
        for loop in self.list_open_loops(person_id=person_id, limit=20):
            if not is_recall_loop_topic(loop.topic):
                continue
            self._close_open_loop(
                loop_id=loop.id,
                person_id=person_id,
                topic=loop.topic,
                ts=ts,
                source_event_id=source_event_id,
                source_text=source_text,
            )
            closed.append(loop.topic)
        return closed

    def close_open_loops_from_utterance(
        self,
        *,
        person_id: str,
        text: str,
        ts: str,
        source_event_id: str,
    ) -> list[str]:
        """Backward-compatible wrapper — loops only."""
        return self.dismiss_from_utterance(
            person_id=person_id,
            text=text,
            ts=ts,
            source_event_id=source_event_id,
        ).closed_loops

    def create_commitment(
        self,
        *,
        person_id: str,
        text: str,
        due_at: str | None,
        source: str,
        metadata: dict | None = None,
    ) -> dict[str, str]:
        self._ensure_person(person_id)
        commitment_id = f"commit_{uuid.uuid4().hex[:10]}"
        created_at = ensure_iso8601(
            self.events.get_latest_timestamp(person_id=person_id) or "2026-01-01T12:00:00+00:00"
        )
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        with self.db.transaction() as connection:
            connection.execute(
                """
                INSERT INTO commitments(
                    commitment_id,
                    person_id,
                    text,
                    due_at,
                    source,
                    status,
                    created_at,
                    completed_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, 'active', ?, NULL, ?)
                """,
                (commitment_id, person_id, text, due_at, source, created_at, metadata_json),
            )
        self.events.ingest(
            SocialEventCreate(
                ts=created_at,
                source="relationship_mcp",
                kind="commitment_created",
                person_id=person_id,
                correlation_id=commitment_id,
                confidence=0.95,
                payload={"text": text, "due_at": due_at, "source": source},
            )
        )
        return {"commitment_id": commitment_id}

    def complete_commitment(self, commitment_id: str) -> dict[str, str]:
        row = self.db.fetchone(
            "SELECT person_id, text FROM commitments WHERE commitment_id = ?", (commitment_id,)
        )
        if row is None:
            raise ValueError(f"Unknown commitment_id: {commitment_id}")
        completed_at = ensure_iso8601(
            self.events.get_latest_timestamp(person_id=row["person_id"])
            or "2026-01-01T12:00:00+00:00"
        )
        with self.db.transaction() as connection:
            connection.execute(
                """
                UPDATE commitments
                SET status = 'completed', completed_at = ?
                WHERE commitment_id = ?
                """,
                (completed_at, commitment_id),
            )
        self.events.ingest(
            SocialEventCreate(
                ts=completed_at,
                source="relationship_mcp",
                kind="commitment_completed",
                person_id=row["person_id"],
                correlation_id=commitment_id,
                confidence=0.95,
                payload={"text": row["text"]},
            )
        )
        return {"commitment_id": commitment_id}

    def list_active_commitments(
        self, *, person_id: str, limit: int = 20
    ) -> list[CommitmentRecord]:
        rows = self.db.fetchall(
            """
            SELECT commitment_id, text, due_at, source, metadata_json
            FROM commitments
            WHERE person_id = ? AND status = 'active'
            ORDER BY COALESCE(due_at, created_at)
            LIMIT ?
            """,
            (person_id, limit),
        )
        return [
            CommitmentRecord(
                id=row["commitment_id"],
                text=row["text"],
                due_at=row["due_at"],
                source=row["source"],
                metadata=json.loads(row["metadata_json"] or "{}"),
            )
            for row in rows
        ]

    def list_due_commitments(
        self,
        *,
        person_id: str,
        as_of: str,
        timezone: str = DEFAULT_TIMEZONE,
        grace_minutes: int = 20,
        catch_up_hours: int = 24,
        limit: int = 5,
    ) -> list[CommitmentRecord]:
        """Active commitments whose due_at fell within the catch-up window ending at as_of."""
        from zoneinfo import ZoneInfo

        now = parse_timestamp(as_of).astimezone(ZoneInfo(timezone))
        _ = grace_minutes
        catch_up_start = now - timedelta(hours=catch_up_hours)
        rows = self.db.fetchall(
            """
            SELECT commitment_id, text, due_at, source, metadata_json
            FROM commitments
            WHERE person_id = ? AND status = 'active' AND due_at IS NOT NULL
            ORDER BY due_at
            LIMIT ?
            """,
            (person_id, max(limit * 4, 20)),
        )
        due: list[CommitmentRecord] = []
        for row in rows:
            due_at_raw = row["due_at"]
            if not due_at_raw:
                continue
            due_dt = parse_timestamp(str(due_at_raw)).astimezone(ZoneInfo(timezone))
            if due_dt > now:
                continue
            if due_dt < catch_up_start:
                continue
            metadata = json.loads(row["metadata_json"] or "{}")
            last_reminded = metadata.get("last_reminded_at")
            if last_reminded:
                reminded_at = parse_timestamp(str(last_reminded)).astimezone(ZoneInfo(timezone))
                if (now - reminded_at).total_seconds() < 1800:
                    continue
            due.append(
                CommitmentRecord(
                    id=row["commitment_id"],
                    text=row["text"],
                    due_at=row["due_at"],
                    source=row["source"],
                    metadata=metadata,
                )
            )
            if len(due) >= limit:
                break
        return due

    def cancel_commitment(self, commitment_id: str, *, source_text: str = "") -> dict[str, str]:
        """Mark a commitment cancelled (e.g. まー said to forget the plan)."""
        row = self.db.fetchone(
            """
            SELECT person_id, text FROM commitments
            WHERE commitment_id = ? AND status = 'active'
            """,
            (commitment_id,),
        )
        if row is None:
            raise ValueError(f"Unknown or inactive commitment_id: {commitment_id}")
        cancelled_at = ensure_iso8601(
            self.events.get_latest_timestamp(person_id=row["person_id"])
            or "2026-01-01T12:00:00+00:00"
        )
        self._cancel_commitment(
            commitment_id=commitment_id,
            ts=cancelled_at,
            source_text=source_text,
        )
        return {"commitment_id": commitment_id}

    def list_open_loops(self, *, person_id: str, limit: int = 10) -> list[OpenLoopRecord]:
        rows = self.db.fetchall(
            """
            SELECT loop_id, topic, status
            FROM open_loops
            WHERE person_id = ? AND status = 'open'
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (person_id, limit),
        )
        return [
            OpenLoopRecord(id=row["loop_id"], topic=row["topic"], status=row["status"])
            for row in rows
        ]

    def record_boundary(
        self,
        *,
        person_id: str,
        kind: str,
        rule: str,
        source_text: str,
    ) -> dict[str, str]:
        self._ensure_person(person_id)
        boundary_id = f"boundary_{uuid.uuid4().hex[:10]}"
        created_at = ensure_iso8601(
            self.events.get_latest_timestamp(person_id=person_id) or "2026-01-01T12:00:00+00:00"
        )
        with self.db.transaction() as connection:
            connection.execute(
                """
                INSERT INTO person_boundaries(
                    boundary_id,
                    person_id,
                    kind,
                    rule,
                    source_text,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (boundary_id, person_id, kind, rule, source_text, created_at),
            )
        self.events.ingest(
            SocialEventCreate(
                ts=created_at,
                source="relationship_mcp",
                kind="boundary_updated",
                person_id=person_id,
                correlation_id=boundary_id,
                confidence=0.95,
                payload={"kind": kind, "rule": rule, "source_text": source_text},
            )
        )
        return {"boundary_id": boundary_id}

    def get_person_model(self, *, person_id: str) -> PersonModel:
        self.refresh_snapshot(person_id)
        person = self.db.fetchone(
            "SELECT canonical_name, role, updated_at FROM persons WHERE person_id = ?",
            (person_id,),
        )
        if person is None:
            raise ValueError(f"Unknown person_id: {person_id}")
        aliases = [
            str(row["alias"])
            for row in self.db.fetchall(
                "SELECT alias FROM person_aliases WHERE person_id = ? ORDER BY alias",
                (person_id,),
            )
            if row["alias"] != person["canonical_name"]
        ]
        snapshot = self.db.fetchone(
            """
            SELECT relationship_summary, ts
            FROM relationship_snapshots
            WHERE person_id = ?
            ORDER BY ts DESC
            LIMIT 1
            """,
            (person_id,),
        )
        commitments = [
            CommitmentRecord(
                id=row["commitment_id"],
                text=row["text"],
                due_at=row["due_at"],
                source=row["source"],
                metadata=json.loads(row["metadata_json"] or "{}"),
            )
            for row in self.db.fetchall(
                """
                SELECT commitment_id, text, due_at, source, metadata_json
                FROM commitments
                WHERE person_id = ? AND status = 'active'
                ORDER BY COALESCE(due_at, created_at)
                """,
                (person_id,),
            )
        ]
        loops = self.list_open_loops(person_id=person_id)
        rituals = [
            RitualRecord(id=row["ritual_id"], kind=row["kind"], cadence=row["cadence"])
            for row in self.db.fetchall(
                """
                SELECT ritual_id, kind, cadence
                FROM rituals
                WHERE person_id = ?
                ORDER BY updated_at DESC
                """,
                (person_id,),
            )
        ]
        boundaries = [
            str(row["rule"])
            for row in self.db.fetchall(
                "SELECT rule FROM person_boundaries WHERE person_id = ? ORDER BY created_at DESC",
                (person_id,),
            )
        ]
        preferences = self._salient_preferences(person_id, boundaries)
        summary = (
            snapshot["relationship_summary"]
            if snapshot
            else "Relationship summary not available yet."
        )
        return PersonModel(
            person_id=person_id,
            canonical_name=str(person["canonical_name"]),
            aliases=aliases,
            role=person["role"],
            salient_preferences=preferences,
            open_loops=loops,
            active_commitments=commitments,
            rituals=rituals,
            boundaries=boundaries,
            relationship_summary=summary,
            last_updated=str(snapshot["ts"] if snapshot else person["updated_at"]),
        )

    def suggest_followup(self, *, person_id: str, context: str) -> list[SuggestionRecord]:
        latest_ts = self.events.get_latest_timestamp(person_id=person_id)
        since = None
        if latest_ts:
            since = ensure_iso8601(parse_timestamp(latest_ts) - timedelta(days=1))
        events = self.events.fetch_events(
            person_id=person_id, since=since, limit=80, include_global=False
        )
        latest_stress_text = None
        for event in events:
            if event.kind != "human_utterance":
                continue
            text = str(event.payload_json.get("text", ""))
            if any(keyword in text.lower() for keyword in STRESS_KEYWORDS):
                latest_stress_text = text
                break
        text, reason = suggest_followup_text(context, latest_stress_text)
        return [SuggestionRecord(text=text, reason=reason)]

    def refresh_snapshot(self, person_id: str) -> None:
        latest_ts = self.events.get_latest_timestamp(person_id=person_id)
        since = None
        if latest_ts:
            since = ensure_iso8601(parse_timestamp(latest_ts) - timedelta(days=30))
        events = self.events.fetch_events(
            person_id=person_id, since=since, limit=200, include_global=False
        )
        human_messages = [
            str(event.payload_json.get("text", ""))
            for event in events
            if event.kind == "human_utterance"
        ]
        agent_messages = [
            str(event.payload_json.get("text", ""))
            for event in events
            if event.kind == "agent_utterance"
        ]
        metrics = compute_snapshot_metrics(
            interaction_count=len(events),
            human_messages=human_messages,
            agent_messages=agent_messages,
        )
        role_row = self.db.fetchone("SELECT role FROM persons WHERE person_id = ?", (person_id,))
        open_loop_count = len(self.list_open_loops(person_id=person_id, limit=20))
        summary = summarize_relationship(
            role=None if role_row is None else role_row["role"],
            recent_stress=metrics["recent_stress"],
            open_loop_count=open_loop_count,
        )
        ts = latest_ts or ensure_iso8601("2026-01-01T12:00:00+00:00")
        with self.db.transaction() as connection:
            connection.execute(
                """
                INSERT INTO relationship_snapshots(
                    snapshot_id, person_id, ts, warmth, trust, fragility, expected_response_latency,
                    recent_stress, reciprocity_balance, relationship_summary, notes_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"relsnap_{uuid.uuid4().hex[:12]}",
                    person_id,
                    ts,
                    metrics["warmth"],
                    metrics["trust"],
                    metrics["fragility"],
                    metrics["expected_response_latency"],
                    metrics["recent_stress"],
                    metrics["reciprocity_balance"],
                    summary,
                    json.dumps({"heuristic": True}, ensure_ascii=False),
                ),
            )

    def _ensure_person(self, person_id: str) -> None:
        if (
            self.db.fetchone("SELECT person_id FROM persons WHERE person_id = ?", (person_id,))
            is not None
        ):
            return
        self.upsert_person(person_id=person_id, canonical_name=person_id, aliases=[], role=None)

    def _update_open_loops(
        self,
        *,
        person_id: str,
        text: str,
        source_event_id: str,
        ts: str,
        direction: str = "human_to_ai",
        timezone: str = DEFAULT_TIMEZONE,
    ) -> None:
        topic = self._extract_topic(text, direction=direction)
        if topic is None:
            return
        today = as_of_date(as_of_ts=ts, tz_name=timezone)
        stale_day = is_stale(
            topic=topic,
            updated_at=ts,
            tz_name=timezone,
            as_of=today,
        )
        existing = self.db.fetchone(
            """
            SELECT loop_id FROM open_loops
            WHERE person_id = ? AND topic = ? AND status = 'open'
            """,
            (person_id, topic),
        )
        if stale_day is not None:
            if existing is not None:
                detail = {
                    "kind": "stale",
                    "reason": "relative_date_passed",
                    "resolved_date": stale_day.isoformat(),
                    "source_topic": topic[:200],
                }
                with self.db.transaction() as connection:
                    connection.execute(
                        """
                        UPDATE open_loops
                        SET status = 'closed', updated_at = ?, source_event_id = ?,
                            detail_json = ?
                        WHERE loop_id = ?
                        """,
                        (
                            ts,
                            source_event_id,
                            json.dumps(detail, ensure_ascii=False),
                            existing["loop_id"],
                        ),
                    )
            return

        resolved = resolve_relative_date(topic=topic, updated_at=ts, tz_name=timezone)
        detail: dict[str, str] = {"kind": "future_task_or_question"}
        if resolved is not None:
            detail["resolved_date"] = resolved.isoformat()

        with self.db.transaction() as connection:
            if existing is not None:
                connection.execute(
                    """
                    UPDATE open_loops
                    SET updated_at = ?, source_event_id = ?, detail_json = ?
                    WHERE loop_id = ?
                    """,
                    (
                        ts,
                        source_event_id,
                        json.dumps(detail, ensure_ascii=False),
                        existing["loop_id"],
                    ),
                )
                return
            connection.execute(
                """
                INSERT INTO open_loops(
                    loop_id,
                    person_id,
                    topic,
                    status,
                    source_event_id,
                    updated_at,
                    detail_json
                )
                VALUES (?, ?, ?, 'open', ?, ?, ?)
                """,
                (
                    f"loop_{uuid.uuid4().hex[:10]}",
                    person_id,
                    topic,
                    source_event_id,
                    ts,
                    json.dumps(detail, ensure_ascii=False),
                ),
            )

    def _maybe_create_reminder_commitment(
        self,
        *,
        person_id: str,
        text: str,
        ts: str,
        timezone: str = DEFAULT_TIMEZONE,
    ) -> dict[str, str] | None:
        spec = extract_reminder_request(text, ts=ts, tz_name=timezone)
        if spec is None:
            return None
        for commitment in self.list_active_commitments(person_id=person_id, limit=50):
            if commitment.due_at == spec.due_at:
                return None
        metadata = {
            "speak_line": spec.speak_line,
            "delivery": spec.delivery,
            "source_utterance": text[:240],
        }
        return self.create_commitment(
            person_id=person_id,
            text=spec.title,
            due_at=spec.due_at,
            source="reminder_request",
            metadata=metadata,
        )

    def _extract_topic(self, text: str, *, direction: str = "human_to_ai") -> str | None:
        if direction != "human_to_ai":
            return None
        if is_dismiss_utterance(text):
            return None
        if is_recall_utterance(text):
            return None
        lowered = text.lower()
        if any(marker in lowered or marker in text for marker in FUTURE_MARKERS):
            if "dentist" in lowered or "歯医者" in text:
                return "dentist"
            if "pr" in lowered and ("review" in lowered or "レビュー" in text):
                return "pr review"
            return _normalize_topic(text)
        return None

    def _loop_matches_dismiss(
        self,
        loop_topic: str,
        text: str,
        explicit_topic: str | None,
    ) -> bool:
        return self._matches_dismiss_target(loop_topic, text, explicit_topic)

    def _matches_dismiss_target(
        self,
        target: str,
        text: str,
        explicit_topic: str | None,
    ) -> bool:
        if explicit_topic and target == explicit_topic:
            return True
        target_lower = target.lower()
        text_lower = text.lower()
        if target_lower in text_lower or target_lower in text:
            return True
        tokens = [word for word in target_lower.split() if len(word) >= 2]
        if tokens and all(word in text_lower or word in text for word in tokens):
            return True
        if explicit_topic:
            explicit_lower = explicit_topic.lower()
            if explicit_lower in target_lower or target_lower in explicit_lower:
                return True
        return False

    def _cancel_commitment(
        self,
        *,
        commitment_id: str,
        ts: str,
        source_text: str,
    ) -> None:
        with self.db.transaction() as connection:
            connection.execute(
                """
                UPDATE commitments
                SET status = 'cancelled', completed_at = ?, metadata_json = ?
                WHERE commitment_id = ? AND status = 'active'
                """,
                (
                    ts,
                    json.dumps(
                        {
                            "kind": "dismissed",
                            "source_text": source_text[:240],
                        },
                        ensure_ascii=False,
                    ),
                    commitment_id,
                ),
            )

    def _close_open_loop(
        self,
        *,
        loop_id: str,
        person_id: str,
        topic: str,
        ts: str,
        source_event_id: str,
        source_text: str,
    ) -> None:
        with self.db.transaction() as connection:
            connection.execute(
                """
                UPDATE open_loops
                SET status = 'closed', updated_at = ?, source_event_id = ?,
                    detail_json = ?
                WHERE loop_id = ? AND person_id = ? AND status = 'open'
                """,
                (
                    ts,
                    source_event_id,
                    json.dumps(
                        {
                            "kind": "dismissed",
                            "source_text": source_text[:240],
                        },
                        ensure_ascii=False,
                    ),
                    loop_id,
                    person_id,
                ),
            )

    def _salient_preferences(
        self, person_id: str, boundaries: list[str]
    ) -> list[PreferenceRecord]:
        preferences: list[PreferenceRecord] = [
            PreferenceRecord(
                text="likes contextual continuity more than generic encouragement",
                confidence=0.55,
                evidence=["heuristic: default posture for relationship continuity"],
                source="inferred",
            )
        ]
        boundary_match = next(
            (b for b in boundaries if "quiet" in b or "midnight" in b), None
        )
        if boundary_match:
            preferences.insert(
                0,
                PreferenceRecord(
                    text="prefers gentle brief nudges while working",
                    confidence=0.78,
                    evidence=[f"boundary: {boundary_match}"],
                    source="inferred",
                ),
            )
        else:
            row = self.db.fetchone(
                """
                SELECT event_id
                FROM events
                WHERE person_id = ?
                  AND kind = 'human_utterance'
                  AND payload_json LIKE '%静か%'
                ORDER BY ts DESC
                LIMIT 1
                """,
                (person_id,),
            )
            if row:
                preferences.insert(
                    0,
                    PreferenceRecord(
                        text="prefers quieter interaction when focused",
                        confidence=0.7,
                        evidence=[f"utterance evidence: event={row['event_id']}"],
                        source="inferred",
                    ),
                )
        return preferences[:3]


def _normalize_topic(text: str) -> str:
    compact = re.sub(r"\s+", " ", text.strip("。.!?？ "))
    return compact[:48]


def _commitment_label(text: str) -> str:
    compact = re.sub(r"\s+", " ", (text or "").strip())
    return compact[:48] if compact else "commitment"
