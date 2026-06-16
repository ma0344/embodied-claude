"""Claude Code permissions.allow UI backend."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from presence_ui.main import create_app


@pytest.fixture
def settings_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / ".claude" / "settings.local.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "env": {"ANTHROPIC_AUTH_TOKEN": "secret"},
                "permissions": {
                    "allow": [
                        "WebFetch",
                        "mcp__memory__*",
                        "Read(//c/Users/ma/src/embodied-claude/**)",
                        "Bash(uv run *)",
                    ]
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "presence_ui.services.claude_permissions.embodied_repo_root",
        lambda: tmp_path,
    )
    return path


def test_list_permission_state(settings_file: Path) -> None:
    from presence_ui.services.claude_permissions import list_permission_state

    presets, preserved = list_permission_state()
    enabled = {p.id for p in presets if p.enabled}
    assert "web_fetch" in enabled
    assert "memory" in enabled
    assert "wifi_cam" not in enabled
    assert "Read(//c/Users/ma/src/embodied-claude/**)" in preserved
    assert "Bash(uv run *)" in preserved


def test_save_enabled_preset_ids(settings_file: Path) -> None:
    from presence_ui.services.claude_permissions import list_permission_state, save_enabled_preset_ids

    save_enabled_preset_ids(["memory", "wifi_cam", "tts"])
    presets, preserved = list_permission_state()
    enabled = {p.rule for p in presets if p.enabled}
    assert enabled == {"mcp__memory__*", "mcp__wifi-cam__*", "mcp__tts__*"}
    assert "Read(//c/Users/ma/src/embodied-claude/**)" in preserved
    assert "Bash(uv run *)" in preserved
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert data["env"]["ANTHROPIC_AUTH_TOKEN"] == "secret"


def test_get_claude_permissions_api(settings_file: Path) -> None:
    client = TestClient(create_app())
    res = client.get("/api/v1/claude/permissions")
    assert res.status_code == 200
    body = res.json()
    assert body["editable"] is True
    assert any(p["id"] == "web_fetch" and p["enabled"] for p in body["presets"])
    assert "ANTHROPIC_AUTH_TOKEN" not in json.dumps(body)


def test_post_claude_permissions_localhost(settings_file: Path) -> None:
    client = TestClient(create_app())
    res = client.post(
        "/api/v1/claude/permissions",
        json={"enabled_ids": ["memory", "sociality"]},
    )
    assert res.status_code == 200
    enabled = {p["rule"] for p in res.json()["presets"] if p["enabled"]}
    assert enabled == {"mcp__memory__*", "mcp__sociality__*"}


def test_post_unknown_preset(settings_file: Path) -> None:
    client = TestClient(create_app())
    res = client.post(
        "/api/v1/claude/permissions",
        json={"enabled_ids": ["not_a_preset"]},
    )
    assert res.status_code == 400
