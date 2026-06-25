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

from .date_resolution import (
    DEFAULT_TIMEZONE,
    anchor_temporal_in_text,
    as_of_date,
    is_stale,
    stale_from_detail_json,
)
from .inference import (
    FUTURE_MARKERS,
    STRESS_KEYWORDS,
    compute_snapshot_metrics,
    extract_archive_remember_content,
    extract_dismiss_topic,
    has_remember_save_trigger,
    is_archive_remember_utterance,
    is_dismiss_utterance,
    is_recall_loop_topic,
    is_recall_utterance,
    suggest_followup_text,
    summarize_relationship,
)
from .reminder_intent import (
    ReminderSpec,
    extract_reminder_request,
    extract_speak_line_followup,
)
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
            SELECT loop_id, topic, updated_at, detail_json
            FROM open_loops
            WHERE person_id = ? AND status = 'open'
            ORDER BY updated_at DESC
            """,
            (person_id,),
        )
        closed_topics: list[str] = []
        for loop_id, topic, updated_at, detail_json in rows:
            passed = stale_from_detail_json(
                str(detail_json or ""),
                as_of=as_of_day,
                include_today=include_today,
            )
            if passed is None:
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
        self._maybe_patch_reminder_speak_line(
            person_id=person_id,
            text=text,
            ts=ts,
        )
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

    def close_loops_after_remember_save(
        self,
        *,
        person_id: str,
        utterance: str,
        saved_content: str | None,
        ts: str,
        source_event_id: str = "",
    ) -> list[str]:
        """Close open loops superseded by successful LTM/gist archival (MEM-8f / OL-ARCHIVE 1)."""
        if not has_remember_save_trigger(utterance):
            return []
        archive_content = extract_archive_remember_content(utterance)
        if not archive_content and not saved_content:
            return []

        closed: list[str] = []
        for loop in self.list_open_loops(person_id=person_id, limit=20):
            if not self._matches_archive_remember_target(
                loop.topic,
                utterance=utterance,
                archive_content=archive_content,
                saved_content=saved_content,
            ):
                continue
            self._close_open_loop(
                loop_id=loop.id,
                person_id=person_id,
                topic=loop.topic,
                ts=ts,
                source_event_id=source_event_id,
                source_text=utterance,
                close_kind="archived_remember",
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
            SELECT commitment_id, text, due_at, source, metadata_json, created_at
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
            if metadata.get("delivery", "say") == "say" and not metadata.get("speak_line"):
                created_raw = row["created_at"]
                if created_raw:
                    try:
                        created_dt = parse_timestamp(str(created_raw)).astimezone(
                            ZoneInfo(timezone)
                        )
                        if (now - created_dt).total_seconds() < 300:
                            continue
                    except (TypeError, ValueError):
                        pass
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

    def patch_commitment_speak_line(
        self, commitment_id: str, *, speak_line: str
    ) -> dict[str, str]:
        """Patch speak_line used by reminder delivery.

        UI edit path: updates commitments.metadata_json["speak_line"] and keeps commitment.text intact.
        """
        speak_line_clean = (speak_line or "").strip()
        if not speak_line_clean:
            raise ValueError("speak_line must not be empty")
        return self._patch_commitment_speak_line(
            commitment_id=commitment_id,
            speak_line=speak_line_clean,
            title=None,
        )

    def list_open_loops(self, *, person_id: str, limit: int = 10) -> list[OpenLoopRecord]:
        rows = self.db.fetchall(
            """
            SELECT loop_id, topic, status, updated_at, detail_json
            FROM open_loops
            WHERE person_id = ? AND status = 'open'
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (person_id, limit),
        )
        records: list[OpenLoopRecord] = []
        for row in rows:
            topic = self._ensure_anchored_loop_topic(
                loop_id=str(row["loop_id"]),
                topic=str(row["topic"]),
                updated_at=str(row["updated_at"]),
                detail_json=str(row["detail_json"] or ""),
                persist=True,
            )
            detail = self._parse_loop_detail(str(row["detail_json"] or ""))
            records.append(
                OpenLoopRecord(
                    id=row["loop_id"],
                    topic=topic,
                    status=row["status"],
                    needs_date_confirmation=bool(detail.get("needs_date_confirmation")),
                    ambiguous_phrases=list(detail.get("ambiguous_phrases") or []),
                )
            )
        return records

    @staticmethod
    def _parse_loop_detail(detail_json: str) -> dict:
        if not detail_json:
            return {}
        try:
            return json.loads(detail_json)
        except json.JSONDecodeError:
            return {}

    def _ensure_anchored_loop_topic(
        self,
        *,
        loop_id: str,
        topic: str,
        updated_at: str,
        detail_json: str,
        persist: bool,
        timezone: str = DEFAULT_TIMEZONE,
    ) -> str:
        anchored_result = anchor_temporal_in_text(
            topic, updated_at=updated_at, tz_name=timezone
        )
        if anchored_result.needs_date_confirmation:
            return topic

        anchored = anchored_result.text
        resolved = anchored_result.resolved_date
        if anchored == topic:
            return topic

        detail = self._parse_loop_detail(detail_json)
        if not detail.get("original_topic"):
            detail["original_topic"] = topic
        if resolved is not None:
            detail["resolved_date"] = resolved.isoformat()
        detail.setdefault("kind", "future_task_or_question")

        if persist:
            with self.db.transaction() as connection:
                connection.execute(
                    """
                    UPDATE open_loops
                    SET topic = ?, detail_json = ?
                    WHERE loop_id = ?
                    """,
                    (
                        anchored,
                        json.dumps(detail, ensure_ascii=False),
                        loop_id,
                    ),
                )
        return anchored

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

    def record_self_disclosure_gist(
        self,
        *,
        person_id: str,
        text: str,
        gist: str,
        ts: str,
        source_event_id: str | None = None,
    ) -> None:
        """MEM-8e: append a compact gist to persons.profile_json (L0 retrieve)."""
        self._ensure_person(person_id)
        gist_text = gist.strip()
        if not gist_text:
            return
        row = self.db.fetchone(
            "SELECT profile_json FROM persons WHERE person_id = ?",
            (person_id,),
        )
        if row is None:
            return
        try:
            profile = json.loads(str(row["profile_json"] or "{}"))
        except json.JSONDecodeError:
            profile = {}
        if not isinstance(profile, dict):
            profile = {}
        entries: list[dict[str, str]] = [
            item
            for item in profile.get("self_disclosure_gists", [])
            if isinstance(item, dict) and item.get("gist") != gist_text
        ]
        entries.insert(
            0,
            {
                "gist": gist_text,
                "text": text[:500],
                "ts": ensure_iso8601(ts),
                **({"source_event_id": source_event_id} if source_event_id else {}),
            },
        )
        profile["self_disclosure_gists"] = entries[:10]
        with self.db.transaction() as connection:
            connection.execute(
                """
                UPDATE persons
                SET profile_json = ?, updated_at = ?
                WHERE person_id = ?
                """,
                (json.dumps(profile, ensure_ascii=False), ensure_iso8601(ts), person_id),
            )

    def _profile_gists_for(self, person_id: str) -> list[str]:
        row = self.db.fetchone(
            "SELECT profile_json FROM persons WHERE person_id = ?",
            (person_id,),
        )
        if row is None:
            return []
        try:
            profile = json.loads(str(row["profile_json"] or "{}"))
        except json.JSONDecodeError:
            return []
        if not isinstance(profile, dict):
            return []
        gists: list[str] = []
        for item in profile.get("self_disclosure_gists", []):
            if isinstance(item, dict):
                gist = str(item.get("gist") or "").strip()
                if gist and gist not in gists:
                    gists.append(gist)
        return gists[:5]

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
            profile_gists=self._profile_gists_for(person_id),
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
        anchored_result = anchor_temporal_in_text(
            topic, updated_at=ts, tz_name=timezone
        )
        if anchored_result.needs_date_confirmation:
            anchored_topic = topic
            resolved = None
        else:
            anchored_topic = anchored_result.text
            resolved = anchored_result.resolved_date
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
            (person_id, anchored_topic),
        )
        if stale_day is not None:
            if existing is not None:
                detail = {
                    "kind": "stale",
                    "reason": "relative_date_passed",
                    "resolved_date": stale_day.isoformat(),
                    "source_topic": topic[:200],
                    "original_topic": topic[:200],
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

        detail: dict[str, object] = {"kind": "future_task_or_question"}
        if anchored_result.needs_date_confirmation:
            detail["needs_date_confirmation"] = True
            detail["ambiguous_phrases"] = list(anchored_result.ambiguous_phrases)
        elif resolved is not None:
            detail["resolved_date"] = resolved.isoformat()
        if anchored_topic != topic:
            detail["original_topic"] = topic[:200]

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
                    anchored_topic,
                    source_event_id,
                    ts,
                    json.dumps(detail, ensure_ascii=False),
                ),
            )

    def _maybe_patch_reminder_speak_line(
        self,
        *,
        person_id: str,
        text: str,
        ts: str,
    ) -> dict[str, str] | None:
        """Fill speak_line on a recent active reminder when user confirms the phrase."""
        speak_line = extract_speak_line_followup(text)
        if not speak_line:
            return None
        try:
            as_of = parse_timestamp(ts)
        except (TypeError, ValueError):
            return None
        rows = self.db.fetchall(
            """
            SELECT commitment_id, text, due_at, metadata_json, created_at
            FROM commitments
            WHERE person_id = ? AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 15
            """,
            (person_id,),
        )
        for row in rows:
            metadata = json.loads(row["metadata_json"] or "{}")
            if metadata.get("speak_line"):
                continue
            due_raw = row["due_at"]
            if not due_raw:
                continue
            try:
                due = parse_timestamp(str(due_raw))
            except (TypeError, ValueError):
                continue
            if due <= as_of:
                continue
            return self._patch_commitment_speak_line(
                commitment_id=row["commitment_id"],
                speak_line=speak_line,
                title=speak_line[:120],
            )
        return None

    def _patch_commitment_speak_line(
        self,
        *,
        commitment_id: str,
        speak_line: str,
        title: str | None = None,
    ) -> dict[str, str]:
        row = self.db.fetchone(
            "SELECT metadata_json FROM commitments WHERE commitment_id = ?",
            (commitment_id,),
        )
        if row is None:
            raise ValueError(f"Unknown commitment_id: {commitment_id}")
        metadata = json.loads(row["metadata_json"] or "{}")
        metadata["speak_line"] = speak_line[:240]
        metadata_json = json.dumps(metadata, ensure_ascii=False)
        with self.db.transaction() as connection:
            if title:
                connection.execute(
                    """
                    UPDATE commitments
                    SET metadata_json = ?, text = ?
                    WHERE commitment_id = ?
                    """,
                    (metadata_json, title[:120], commitment_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE commitments
                    SET metadata_json = ?
                    WHERE commitment_id = ?
                    """,
                    (metadata_json, commitment_id),
                )
        return {"commitment_id": commitment_id, "speak_line": speak_line[:240]}

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
        return self.create_reminder_from_spec(
            person_id=person_id,
            spec=spec,
            source_utterance=text,
        )

    def create_reminder_from_spec(
        self,
        *,
        person_id: str,
        spec: ReminderSpec,
        source_utterance: str,
        source: str = "reminder_request",
    ) -> dict[str, str] | None:
        """Persist a parsed reminder spec if no active commitment shares due_at."""
        for commitment in self.list_active_commitments(person_id=person_id, limit=50):
            if commitment.due_at == spec.due_at:
                return None
        metadata = {
            "speak_line": spec.speak_line,
            "delivery": spec.delivery,
            "source_utterance": source_utterance[:240],
            "spec_source": source,
        }
        return self.create_commitment(
            person_id=person_id,
            text=spec.title,
            due_at=spec.due_at,
            source=source,
            metadata=metadata,
        )

    def _extract_topic(self, text: str, *, direction: str = "human_to_ai") -> str | None:
        if direction != "human_to_ai":
            return None
        if is_dismiss_utterance(text):
            return None
        if is_recall_utterance(text):
            return None
        if is_archive_remember_utterance(text):
            return None
        lowered = text.lower()
        if any(marker in lowered or marker in text for marker in FUTURE_MARKERS):
            if "dentist" in lowered or "歯医者" in text:
                return "dentist"
            if "pr" in lowered and ("review" in lowered or "レビュー" in text):
                return "pr review"
            return _normalize_topic(text)
        return None

    def _matches_archive_remember_target(
        self,
        loop_topic: str,
        *,
        utterance: str,
        archive_content: str | None,
        saved_content: str | None,
    ) -> bool:
        norm_utter = _normalize_topic(utterance)
        if loop_topic == norm_utter:
            return True
        for candidate in (archive_content, saved_content):
            if not candidate:
                continue
            norm = _normalize_topic(candidate)
            if loop_topic == norm:
                return True
            if len(norm) >= 4 and (norm in loop_topic or loop_topic in norm):
                return True
        explicit = archive_content or saved_content
        if explicit and self._matches_dismiss_target(
            loop_topic, utterance, _normalize_topic(explicit)
        ):
            return True
        return False

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
        close_kind: str = "dismissed",
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
                            "kind": close_kind,
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
