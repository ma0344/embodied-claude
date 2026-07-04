"""Surface session JSONL store."""

from __future__ import annotations

from pathlib import Path

import pytest

from presence_ui.gateway import surface_session as ss
from presence_ui.services.native_history import (
    fetch_native_session_messages,
    list_native_sessions,
)


@pytest.fixture
def surface_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "sessions"
    monkeypatch.setenv("PRESENCE_SURFACE_SESSIONS_DIR", str(root))
    return root


def test_append_and_load_turns(surface_dir: Path) -> None:
    sid = "abc12345-aaaa-bbbb-cccc-ddddeeeeffff"
    ss.append_surface_turn(
        session_id=sid,
        role="user",
        text="おはよう",
        enriched="[gateway_turn_context]\nctx\n\nおはよう",
        timestamp="2026-07-03T10:00:00+09:00",
    )
    ss.append_surface_turn(
        session_id=sid,
        role="assistant",
        text="おはよう、まー",
        timestamp="2026-07-03T10:00:01+09:00",
    )
    turns = ss.load_surface_turns(sid)
    assert len(turns) == 2
    assert turns[0].text == "おはよう"
    assert turns[0].enriched is not None
    assert turns[1].text == "おはよう、まー"


def test_surface_sessions_dir_ignores_comment_like_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(
        "PRESENCE_SURFACE_SESSIONS_DIR",
        "# 省略時 ~/.claude/koyori-surface/sessions",
    )
    path = ss.surface_sessions_dir()
    assert "#" not in str(path)
    assert path.name == "sessions"
    assert path.parent.name == "koyori-surface"


def test_native_history_reads_surface_jsonl(surface_dir: Path) -> None:
    sid = "abc12345-aaaa-bbbb-cccc-ddddeeeeffff"
    ss.append_surface_turn(
        session_id=sid,
        role="user",
        text="ねえ",
        timestamp="2026-07-03T11:00:00+09:00",
    )
    ss.append_surface_turn(
        session_id=sid,
        role="assistant",
        text="なに？",
        timestamp="2026-07-03T11:00:01+09:00",
    )
    listed = list_native_sessions(limit=10)
    row = next(item for item in listed.sessions if item.session_id == sid)
    assert row.title == "ねえ"
    fetched = fetch_native_session_messages(sid)
    assert fetched is not None
    assert len(fetched.messages) == 2
    assert fetched.messages[1].message == "なに？"
