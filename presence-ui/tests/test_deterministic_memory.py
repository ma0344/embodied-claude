"""Deterministic remember intent detection and HTTP persistence."""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from presence_ui.gateway import deterministic_memory as dm


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ミッションAのE2Eを覚えておいて", "ミッションAのE2E"),
        ("覚えておいて: 明日は買い物", "明日は買い物"),
        (
            "今度は「まーと話すときは、必ず日本語で」を覚えておいて",
            "まーと話すときは、必ず日本語で",
        ),
        (
            "「Cursorに渡すプロンプトは日本語で作成する」を覚えておいて",
            "Cursorに渡すプロンプトは日本語で作成する",
        ),
        ("もう一度「煎餅が好き」を覚えておいて", "煎餅が好き"),
        ("hello world", None),
        ("覚えておいて", None),
    ],
)
def test_detect_remember_intent(text: str, expected: str | None) -> None:
    intent = dm.detect_remember_intent(text)
    if expected is None:
        assert intent is None
    else:
        assert intent is not None
        assert intent.content == expected


@pytest.mark.parametrize(
    ("text", "expected_substr"),
    [
        ("僕は北海道の中標津町で生まれたんだ。", "中標津町"),
        ("僕が一番最初に買ってもらったPCはMSXだったよ", "MSX"),
        ("僕の出身地は北海道の中標津町だよ", "中標津町"),
        ("小さい頃、何か飼ってた？", None),
        ("僕の好きなものの話は覚えてる？", None),
        ("直近10件の記憶リストを出して。", None),
    ],
)
def test_detect_personal_fact_intent(text: str, expected_substr: str | None) -> None:
    intent = dm.detect_personal_fact_intent(text)
    if expected_substr is None:
        assert intent is None
    else:
        assert intent is not None
        assert expected_substr in intent.content
        assert intent.category == "memory"


@pytest.mark.parametrize(
    ("text", "limit", "oldest_first"),
    [
        ("最初から10個分の記憶を完全なリストで出して", 10, True),
        ("直近10件の記憶リストを出して。", 10, False),
        ("最近の記憶をリストで見せて", 10, False),
        ("記憶5個一覧", 5, False),
        ("/memories", 10, False),
        ("memories", 10, False),
        ("/memories 5", 5, False),
        ("hello", None, None),
    ],
)
def test_detect_memory_list_request(
    text: str, limit: int | None, oldest_first: bool | None
) -> None:
    req = dm.detect_memory_list_request(text)
    if limit is None:
        assert req is None
    else:
        assert req is not None
        assert req.limit == limit
        assert req.oldest_first is oldest_first


def test_fetch_memory_list_oldest_first(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE memories (
                id TEXT PRIMARY KEY, content TEXT NOT NULL, normalized_content TEXT NOT NULL,
                timestamp TEXT NOT NULL, emotion TEXT NOT NULL DEFAULT 'neutral',
                importance INTEGER NOT NULL DEFAULT 3, category TEXT NOT NULL DEFAULT 'daily',
                access_count INTEGER NOT NULL DEFAULT 0, last_accessed TEXT NOT NULL DEFAULT '',
                linked_ids TEXT NOT NULL DEFAULT '', episode_id TEXT,
                sensory_data TEXT NOT NULL DEFAULT '', camera_position TEXT,
                tags TEXT NOT NULL DEFAULT '', links TEXT NOT NULL DEFAULT '',
                novelty_score REAL NOT NULL DEFAULT 0.0, prediction_error REAL NOT NULL DEFAULT 0.0,
                activation_count INTEGER NOT NULL DEFAULT 0,
                last_activated TEXT NOT NULL DEFAULT '',
                reading TEXT, pan_angle REAL, tilt_angle REAL
            );
            INSERT INTO memories (id, content, normalized_content, timestamp, emotion, category)
            VALUES ('a', 'first', 'first', '2026-01-01T00:00:00', 'neutral', 'daily'),
                   ('b', 'second', 'second', '2026-06-01T00:00:00', 'neutral', 'daily');
            """
        )
    with patch("memory_auto_save.memory_db_path", return_value=db_path):
        rows = dm.fetch_memory_list(limit=1, oldest_first=True)
    assert len(rows) == 1
    assert rows[0]["content"] == "first"


def test_persist_remember_intent_success() -> None:
    payload = b'{"ok": true, "id": "mem-1", "duplicate": false}'
    response = MagicMock()
    response.read.return_value = payload
    response.__enter__.return_value = response

    patch_http = "memory_auto_save._http_memory_available"
    with patch(patch_http, return_value=True):
        with patch("urllib.request.urlopen", return_value=response):
            outcome = dm.persist_remember_intent(dm.RememberIntent(content="test fact"))

    assert outcome.ok is True
    assert outcome.memory_id == "mem-1"
    assert outcome.duplicate is False
    assert outcome.via == "http"


def test_persist_remember_intent_http_error() -> None:
    import urllib.error

    patch_http = "memory_auto_save._http_memory_available"
    with patch(patch_http, return_value=True):
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            with patch(
                "memory_auto_save._sqlite_remember_fallback",
                return_value=dm.RememberOutcome(ok=False, content="x", error="no db"),
            ) as sqlite_fb:
                outcome = dm.persist_remember_intent(dm.RememberIntent(content="x"))

    sqlite_fb.assert_called_once()
    assert outcome.ok is False
    assert outcome.error


def test_persist_remember_intent_sqlite_fallback_when_http_down(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    db_path.write_bytes(b"")
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                normalized_content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                emotion TEXT NOT NULL DEFAULT 'neutral',
                importance INTEGER NOT NULL DEFAULT 3,
                category TEXT NOT NULL DEFAULT 'daily',
                access_count INTEGER NOT NULL DEFAULT 0,
                last_accessed TEXT NOT NULL DEFAULT '',
                linked_ids TEXT NOT NULL DEFAULT '',
                episode_id TEXT,
                sensory_data TEXT NOT NULL DEFAULT '',
                camera_position TEXT,
                tags TEXT NOT NULL DEFAULT '',
                links TEXT NOT NULL DEFAULT '',
                novelty_score REAL NOT NULL DEFAULT 0.0,
                prediction_error REAL NOT NULL DEFAULT 0.0,
                activation_count INTEGER NOT NULL DEFAULT 0,
                last_activated TEXT NOT NULL DEFAULT '',
                reading TEXT,
                pan_angle REAL,
                tilt_angle REAL
            );
            """
        )

    patch_http = "memory_auto_save._http_memory_available"
    patch_db = "memory_auto_save.memory_db_path"
    with patch(patch_http, return_value=False):
        with patch(patch_db, return_value=db_path):
            outcome = dm.persist_remember_intent(
                dm.RememberIntent(content="Cursorプロンプトは日本語", category="technical")
            )

    assert outcome.ok is True
    assert outcome.via == "sqlite"
    assert outcome.duplicate is False
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT content, category FROM memories").fetchone()
    assert row[0] == "Cursorプロンプトは日本語"
    assert row[1] == "technical"


def test_memory_saved_prompt_note() -> None:
    ok = dm.memory_saved_prompt_note(
        dm.RememberOutcome(ok=True, content="foo", memory_id="id-1")
    )
    assert "[memory_saved_server]" in ok
    assert "mcp__memory__remember" in ok

    fail = dm.memory_saved_prompt_note(
        dm.RememberOutcome(ok=False, content="foo", error="timeout")
    )
    assert "[memory_save_failed]" in fail
    assert "NOT say you remembered" in fail
