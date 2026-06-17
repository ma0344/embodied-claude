"""Tests for IBF-4 kiosk MCP profile validation."""

from __future__ import annotations

import json
from pathlib import Path

from presence_ui.gateway import kiosk_mcp


def test_validate_kiosk_mcp_ok(tmp_path: Path, monkeypatch) -> None:
    settings = tmp_path / "settings.local.json"
    settings.write_text(
        json.dumps({"enabledMcpjsonServers": ["system-temperature"]}),
        encoding="utf-8",
    )
    monkeypatch.delenv("PRESENCE_KIOSK_MCP_SERVERS", raising=False)
    ok, message = kiosk_mcp.validate_kiosk_mcp_profile(settings_path=settings)
    assert ok is True
    assert "system-temperature" in message


def test_validate_kiosk_mcp_extra_servers(tmp_path: Path, monkeypatch) -> None:
    settings = tmp_path / "settings.local.json"
    settings.write_text(
        json.dumps({"enabledMcpjsonServers": ["system-temperature", "tts", "memory"]}),
        encoding="utf-8",
    )
    monkeypatch.delenv("PRESENCE_KIOSK_MCP_SERVERS", raising=False)
    ok, message = kiosk_mcp.validate_kiosk_mcp_profile(settings_path=settings)
    assert ok is False
    assert "extra=" in message
    assert "tts" in message
