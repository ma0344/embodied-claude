"""WS-1/WS-3 guard — permissions, intent detection, stable append."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from presence_ui.gateway.ws_guard import (
    apply_ws_guard_to_settings,
    ensure_ws_guard_permissions,
    filter_managed_preset_ids,
    looks_like_web_search_request,
    ws_guard_stable_append,
)
from presence_ui.services.claude_permissions import list_permission_state, save_enabled_preset_ids
from presence_ui.services.llm import build_gateway_stable_append


def test_ws_guard_stable_append_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRESENCE_WS_GUARD", raising=False)
    assert "WebSearch" in ws_guard_stable_append()
    stable = build_gateway_stable_append()
    assert "[Web lookup — WS guard]" in stable


def test_ws_guard_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_WS_GUARD", "0")
    assert ws_guard_stable_append() == ""


@pytest.mark.parametrize(
    "text,expected",
    [
        ("松本市の申請書を調べて", True),
        ("こんにちは", False),
        ("", False),
    ],
)
def test_looks_like_web_search_request(text: str, expected: bool) -> None:
    assert looks_like_web_search_request(text) is expected


def test_apply_ws_guard_to_settings() -> None:
    data = {
        "permissions": {
            "allow": ["WebSearch", "WebFetch", "mcp__memory__*"],
        }
    }
    assert apply_ws_guard_to_settings(data) is True
    assert data["permissions"]["allow"] == ["mcp__memory__*"]
    assert set(data["permissions"]["deny"]) == {"WebSearch", "WebFetch"}
    assert apply_ws_guard_to_settings(data) is False


def test_ensure_ws_guard_permissions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = tmp_path / ".claude" / "settings.local.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(
        json.dumps({"permissions": {"allow": ["WebSearch", "mcp__memory__*"]}}),
        encoding="utf-8",
    )
    monkeypatch.setattr("presence_ui.gateway.ws_guard._repo_root", lambda: tmp_path)
    assert ensure_ws_guard_permissions() is True
    saved = json.loads(settings.read_text(encoding="utf-8"))
    assert "WebSearch" not in saved["permissions"]["allow"]
    assert "WebSearch" in saved["permissions"]["deny"]


def test_filter_managed_preset_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRESENCE_WS_GUARD", raising=False)
    out = filter_managed_preset_ids(["memory", "web_search", "tts"])
    assert out == ["memory", "tts"]


def test_permissions_ui_hides_web_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / ".claude" / "settings.local.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"permissions": {"allow": ["WebFetch", "mcp__memory__*"]}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "presence_ui.services.claude_permissions.embodied_repo_root",
        lambda: tmp_path,
    )
    monkeypatch.delenv("PRESENCE_WS_GUARD", raising=False)
    presets, _ = list_permission_state()
    enabled = {p.id for p in presets if p.enabled}
    assert "web_fetch" not in enabled
    assert "memory" in enabled


def test_save_presets_strips_web_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / ".claude" / "settings.local.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"permissions": {"allow": []}}), encoding="utf-8")
    monkeypatch.setattr(
        "presence_ui.services.claude_permissions.embodied_repo_root",
        lambda: tmp_path,
    )
    monkeypatch.delenv("PRESENCE_WS_GUARD", raising=False)
    save_enabled_preset_ids(["memory", "web_search", "web_fetch"])
    data = json.loads(path.read_text(encoding="utf-8"))
    allow = data["permissions"]["allow"]
    assert "WebSearch" not in allow
    assert "WebFetch" not in allow
    assert "mcp__memory__*" in allow
    assert set(data["permissions"]["deny"]) >= {"WebSearch", "WebFetch"}
