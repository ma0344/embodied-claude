"""SQLite migrations for the shared sociality database."""

from __future__ import annotations

from dataclasses import dataclass
from sqlite3 import Connection

from .time import utc_now


@dataclass(frozen=True, slots=True)
class Migration:
    name: str
    sql: str


_MIGRATION_002_SQL = """
CREATE TABLE IF NOT EXISTS agent_experiences (
    experience_id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    person_id TEXT,
    kind TEXT NOT NULL,
    summary TEXT NOT NULL,
    private_summary TEXT,
    public_summary TEXT,
    why TEXT,
    felt_state_json TEXT NOT NULL DEFAULT '{}',
    desires_before_json TEXT NOT NULL DEFAULT '{}',
    desires_after_json TEXT NOT NULL DEFAULT '{}',
    related_event_ids TEXT NOT NULL DEFAULT '',
    related_memory_ids TEXT NOT NULL DEFAULT '',
    artifacts_json TEXT NOT NULL DEFAULT '[]',
    importance INTEGER NOT NULL DEFAULT 3,
    privacy_level TEXT NOT NULL DEFAULT 'private',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_experiences_ts
    ON agent_experiences(ts DESC, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_experiences_person
    ON agent_experiences(person_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_agent_experiences_kind
    ON agent_experiences(kind, ts DESC);

CREATE TABLE IF NOT EXISTS private_reflections (
    reflection_id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    person_id TEXT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    importance INTEGER NOT NULL DEFAULT 3,
    may_surface_later INTEGER NOT NULL DEFAULT 1,
    surfaced_at TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_private_reflections_ts
    ON private_reflections(ts DESC);
CREATE INDEX IF NOT EXISTS idx_private_reflections_person
    ON private_reflections(person_id, ts DESC);

CREATE TABLE IF NOT EXISTS interpretation_shifts (
    shift_id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    person_id TEXT,
    topic TEXT NOT NULL,
    old_interpretation TEXT NOT NULL,
    new_interpretation TEXT NOT NULL,
    trigger TEXT NOT NULL,
    confidence REAL NOT NULL,
    implications_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_interpretation_shifts_ts
    ON interpretation_shifts(ts DESC);
CREATE INDEX IF NOT EXISTS idx_interpretation_shifts_topic
    ON interpretation_shifts(topic, ts DESC);

CREATE TABLE IF NOT EXISTS private_letters (
    letter_id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    person_id TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    intended_time TEXT,
    visibility TEXT NOT NULL DEFAULT 'private',
    related_open_loops TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_private_letters_person_ts
    ON private_letters(person_id, ts DESC);
"""


MIGRATIONS = [
    Migration(
        name="001_initial_schema",
        sql="""
        CREATE TABLE IF NOT EXISTS events (
            event_seq INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            ts TEXT NOT NULL,
            source TEXT NOT NULL,
            kind TEXT NOT NULL,
            person_id TEXT,
            session_id TEXT,
            correlation_id TEXT,
            confidence REAL NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS social_state_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            ts TEXT NOT NULL,
            person_id TEXT,
            state_json TEXT NOT NULL,
            summary_for_prompt TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS persons (
            person_id TEXT PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            role TEXT,
            profile_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS person_aliases (
            alias_id TEXT PRIMARY KEY,
            person_id TEXT NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
            alias TEXT NOT NULL,
            UNIQUE(person_id, alias),
            UNIQUE(alias)
        );

        CREATE TABLE IF NOT EXISTS relationship_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            person_id TEXT NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
            ts TEXT NOT NULL,
            warmth REAL NOT NULL,
            trust REAL NOT NULL,
            fragility REAL NOT NULL,
            expected_response_latency REAL NOT NULL,
            recent_stress REAL NOT NULL,
            reciprocity_balance REAL NOT NULL,
            relationship_summary TEXT NOT NULL,
            notes_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS commitments (
            commitment_id TEXT PRIMARY KEY,
            person_id TEXT REFERENCES persons(person_id) ON DELETE SET NULL,
            text TEXT NOT NULL,
            due_at TEXT,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            completed_at TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS open_loops (
            loop_id TEXT PRIMARY KEY,
            person_id TEXT REFERENCES persons(person_id) ON DELETE SET NULL,
            topic TEXT NOT NULL,
            status TEXT NOT NULL,
            source_event_id TEXT,
            updated_at TEXT NOT NULL,
            detail_json TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS rituals (
            ritual_id TEXT PRIMARY KEY,
            person_id TEXT REFERENCES persons(person_id) ON DELETE SET NULL,
            kind TEXT NOT NULL,
            cadence TEXT NOT NULL,
            detail_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS person_boundaries (
            boundary_id TEXT PRIMARY KEY,
            person_id TEXT NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            rule TEXT NOT NULL,
            source_text TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scene_frames (
            frame_id TEXT PRIMARY KEY,
            ts TEXT NOT NULL,
            person_id TEXT,
            session_id TEXT,
            camera_pose_json TEXT NOT NULL,
            scene_summary TEXT NOT NULL,
            raw_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scene_people (
            frame_person_id TEXT PRIMARY KEY,
            frame_id TEXT NOT NULL REFERENCES scene_frames(frame_id) ON DELETE CASCADE,
            person_id TEXT,
            display_name TEXT,
            relative_position TEXT,
            distance TEXT,
            gaze_target TEXT,
            confidence REAL NOT NULL,
            raw_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scene_objects (
            frame_object_id TEXT PRIMARY KEY,
            frame_id TEXT NOT NULL REFERENCES scene_frames(frame_id) ON DELETE CASCADE,
            object_id TEXT NOT NULL,
            label TEXT NOT NULL,
            attributes_json TEXT NOT NULL,
            relations_json TEXT NOT NULL,
            salience REAL NOT NULL,
            raw_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS joint_focus (
            focus_id TEXT PRIMARY KEY,
            ts TEXT NOT NULL,
            person_id TEXT,
            target_id TEXT NOT NULL,
            initiator TEXT NOT NULL,
            confidence REAL NOT NULL,
            based_on_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS consents (
            consent_id TEXT PRIMARY KEY,
            person_id TEXT NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
            consent_type TEXT NOT NULL,
            value INTEGER NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT,
            UNIQUE(person_id, consent_type)
        );

        CREATE TABLE IF NOT EXISTS narrative_daybooks (
            daybook_id TEXT PRIMARY KEY,
            day TEXT NOT NULL UNIQUE,
            ts TEXT NOT NULL,
            summary TEXT NOT NULL,
            evidence_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS identity_facets (
            facet_id TEXT PRIMARY KEY,
            facet_key TEXT NOT NULL UNIQUE,
            summary TEXT NOT NULL,
            confidence REAL NOT NULL,
            updated_at TEXT NOT NULL,
            evidence_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS narrative_arcs (
            arc_id TEXT PRIMARY KEY,
            title TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL,
            importance REAL NOT NULL,
            summary TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            notes_json TEXT NOT NULL DEFAULT '{}'
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_events_source_correlation
            ON events(source, correlation_id)
            WHERE correlation_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts DESC, event_seq DESC);
        CREATE INDEX IF NOT EXISTS idx_events_person ON events(person_id, ts DESC);
        CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind, ts DESC);
        CREATE INDEX IF NOT EXISTS idx_commitments_person_status
            ON commitments(person_id, status, due_at);
        CREATE INDEX IF NOT EXISTS idx_open_loops_person_status
            ON open_loops(person_id, status, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_scene_frames_person_ts
            ON scene_frames(person_id, ts DESC);
        CREATE INDEX IF NOT EXISTS idx_joint_focus_person_ts
            ON joint_focus(person_id, ts DESC);
        """,
    ),
    Migration(
        name="002_interaction_orchestrator",
        sql=_MIGRATION_002_SQL,
    ),
    Migration(
        name="003_room_sessions",
        sql="""
        CREATE TABLE IF NOT EXISTS room_sessions (
            session_id TEXT PRIMARY KEY,
            person_id TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );

        CREATE INDEX IF NOT EXISTS idx_room_sessions_person_updated
            ON room_sessions(person_id, updated_at DESC);

        CREATE TABLE IF NOT EXISTS session_pointers (
            client_id TEXT NOT NULL,
            person_id TEXT NOT NULL,
            active_session_id TEXT NOT NULL,
            activated_at TEXT NOT NULL,
            PRIMARY KEY (client_id, person_id),
            FOREIGN KEY (active_session_id) REFERENCES room_sessions(session_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_session_pointers_active
            ON session_pointers(active_session_id, activated_at DESC);
        """,
    ),
    Migration(
        name="004_outbound_nudges",
        sql="""
        CREATE TABLE IF NOT EXISTS outbound_nudges (
            nudge_id TEXT PRIMARY KEY,
            ts TEXT NOT NULL,
            person_id TEXT,
            text TEXT NOT NULL,
            speak INTEGER NOT NULL DEFAULT 1,
            channels_json TEXT NOT NULL DEFAULT '[]',
            desire TEXT,
            text_fingerprint TEXT NOT NULL,
            experience_id TEXT,
            delivered_at TEXT,
            delivered_channels_json TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_outbound_nudges_pending
            ON outbound_nudges(person_id, delivered_at, ts);

        CREATE INDEX IF NOT EXISTS idx_outbound_nudges_cooldown
            ON outbound_nudges(person_id, ts DESC);
        """,
    ),
    Migration(
        name="005_outbound_client_acks",
        sql="""
        CREATE TABLE IF NOT EXISTS outbound_nudge_client_acks (
            nudge_id TEXT NOT NULL,
            client_id TEXT NOT NULL,
            channels_json TEXT NOT NULL DEFAULT '[]',
            acked_at TEXT NOT NULL,
            PRIMARY KEY (nudge_id, client_id),
            FOREIGN KEY (nudge_id) REFERENCES outbound_nudges(nudge_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_outbound_client_acks_client
            ON outbound_nudge_client_acks(client_id, acked_at DESC);
        """,
    ),
    Migration(
        name="006_stm_entries",
        sql="""
        CREATE TABLE IF NOT EXISTS stm_entries (
            entry_id TEXT PRIMARY KEY,
            ts TEXT NOT NULL,
            local_day TEXT NOT NULL,
            person_id TEXT,
            source TEXT NOT NULL,
            kind TEXT NOT NULL,
            summary TEXT NOT NULL,
            session_id TEXT,
            experience_id TEXT,
            turn_index INTEGER,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            importance INTEGER NOT NULL DEFAULT 3,
            dreamed_at TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_stm_entries_ts
            ON stm_entries(ts DESC, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_stm_entries_local_day
            ON stm_entries(local_day DESC, ts DESC);
        CREATE INDEX IF NOT EXISTS idx_stm_entries_person_day
            ON stm_entries(person_id, local_day DESC, ts DESC);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_stm_entries_experience
            ON stm_entries(experience_id)
            WHERE experience_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_stm_entries_undreamed
            ON stm_entries(dreamed_at, local_day)
            WHERE dreamed_at IS NULL;
        """,
    ),
    Migration(
        name="007_session_episode_closures",
        sql="""
        CREATE TABLE IF NOT EXISTS session_episode_closures (
            session_id TEXT PRIMARY KEY,
            stm_entry_id TEXT NOT NULL,
            person_id TEXT,
            trigger TEXT NOT NULL,
            turn_count INTEGER NOT NULL DEFAULT 0,
            closed_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_session_episode_closures_closed
            ON session_episode_closures(closed_at DESC);
        CREATE INDEX IF NOT EXISTS idx_session_episode_closures_person
            ON session_episode_closures(person_id, closed_at DESC);
        """,
    ),
    Migration(
        name="008_interpretation_shift_resolved_date",
        sql="""
        ALTER TABLE interpretation_shifts ADD COLUMN resolved_date TEXT;
        """,
    ),
]


def apply_migrations(connection: Connection) -> None:
    """Apply pending migrations exactly once."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    applied = {
        row[0] for row in connection.execute("SELECT name FROM schema_migrations").fetchall()
    }
    for migration in MIGRATIONS:
        if migration.name in applied:
            continue
        connection.executescript(migration.sql)
        connection.execute(
            "INSERT INTO schema_migrations(name, applied_at) VALUES(?, ?)",
            (migration.name, utc_now()),
        )
    connection.commit()
