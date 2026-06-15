"""Native session prefs and display time tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from presence_ui.main import create_app
from presence_ui.services.display_time import display_timezone, normalize_iso_timestamp
from presence_ui.services.native_history import list_native_sessions
from presence_ui.services.native_session_prefs import hide_session, load_hidden_session_ids
from presence_ui.services.session_log import _encode_project_path

SESSION_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
SESSION_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


@pytest.fixture
def prefs_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "presence-ui"
    home.mkdir()
    monkeypatch.setenv("PRESENCE_UI_HOME", str(home))
    return home


def test_normalize_iso_timestamp_adds_utc_for_naive() -> None:
    assert normalize_iso_timestamp("2026-06-14T19:21:00").endswith("+00:00")


def test_display_timezone_defaults_to_jst(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRESENCE_TIMEZONE", raising=False)
    assert display_timezone() == "Asia/Tokyo"


def test_hide_session_persists(prefs_home: Path) -> None:
    del prefs_home
    hide_session(SESSION_A)
    assert SESSION_A in load_hidden_session_ids()


def test_list_native_sessions_excludes_hidden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prefs_home: Path
) -> None:
    del prefs_home
    project_path = str(tmp_path / "embodied-claude")
    claude_home = tmp_path / ".claude"
    encoded = _encode_project_path(project_path)
    project_dir = claude_home / "projects" / encoded
    project_dir.mkdir(parents=True)

    for sid, text in ((SESSION_A, "visible"), (SESSION_B, "hidden")):
        path = project_dir / f"{sid}.jsonl"
        path.write_text(
            json.dumps(
                {
                    "type": "user",
                    "timestamp": "2026-06-14T10:00:00+00:00",
                    "message": {"content": [{"type": "text", "text": text}]},
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    monkeypatch.setenv("CLAUDE_HOME", str(claude_home))
    monkeypatch.setenv("PRESENCE_PROJECT_PATH", project_path)
    hide_session(SESSION_B)

    result = list_native_sessions(limit=10)
    ids = {row.session_id for row in result.sessions}
    assert SESSION_A in ids
    assert SESSION_B not in ids


def test_hide_http_routes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prefs_home: Path
) -> None:
    del prefs_home
    client = TestClient(create_app())
    hidden = client.post(f"/api/v1/native/sessions/{SESSION_A}/hide")
    assert hidden.status_code == 200
    assert hidden.json()["hidden_count"] == 1

    merge = client.post(
        "/api/v1/native/hidden",
        json={"session_ids": [SESSION_B]},
    )
    assert merge.status_code == 200
    assert merge.json()["hidden_count"] == 2


def test_ui_config_includes_display_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_TIMEZONE", "Asia/Tokyo")
    client = TestClient(create_app())
    body = client.get("/api/v1/ui-config").json()
    assert body["display_timezone"] == "Asia/Tokyo"
