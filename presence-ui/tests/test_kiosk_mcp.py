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


def test_validate_kiosk_mcp_both_paths_aligned(tmp_path: Path, monkeypatch) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    payload = json.dumps({"enabledMcpjsonServers": ["system-temperature"]})
    (tmp_path / "settings.local.json").write_text(payload, encoding="utf-8")
    (claude_dir / "settings.local.json").write_text(payload, encoding="utf-8")
    monkeypatch.setattr(kiosk_mcp, "embodied_repo_root", lambda: tmp_path)
    monkeypatch.delenv("PRESENCE_KIOSK_MCP_SERVERS", raising=False)
    ok, message = kiosk_mcp.validate_kiosk_mcp_profile()
    assert ok is True
    assert "settings.local.json" in message
    assert ".claude/settings.local.json" in message


def test_validate_kiosk_mcp_root_and_claude_mismatch(tmp_path: Path, monkeypatch) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (tmp_path / "settings.local.json").write_text(
        json.dumps({"enabledMcpjsonServers": ["system-temperature", "memory", "sociality"]}),
        encoding="utf-8",
    )
    (claude_dir / "settings.local.json").write_text(
        json.dumps({"enabledMcpjsonServers": ["system-temperature"]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(kiosk_mcp, "embodied_repo_root", lambda: tmp_path)
    monkeypatch.delenv("PRESENCE_KIOSK_MCP_SERVERS", raising=False)
    ok, message = kiosk_mcp.validate_kiosk_mcp_profile()
    assert ok is False
    assert "disagree" in message
    assert "memory" in message


def test_build_strict_mcp_config_filters_servers(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "system-temperature": {"command": "echo", "args": ["temp"]},
                    "memory": {"command": "echo", "args": ["mem"]},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(kiosk_mcp, "embodied_repo_root", lambda: tmp_path)
    monkeypatch.delenv("PRESENCE_KIOSK_MCP_SERVERS", raising=False)
    out = kiosk_mcp.build_strict_mcp_config_file()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert set(data["mcpServers"]) == {"system-temperature"}


def test_validate_claude_json_empty_loads_all(tmp_path: Path, monkeypatch) -> None:
    claude_json = tmp_path / ".claude.json"
    claude_json.write_text(
        json.dumps(
            {
                "projects": {
                    str(tmp_path.resolve()): {"enabledMcpjsonServers": []},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(kiosk_mcp, "claude_json_path", lambda: claude_json)
    monkeypatch.setattr(kiosk_mcp, "embodied_repo_root", lambda: tmp_path)
    monkeypatch.delenv("PRESENCE_KIOSK_MCP_SERVERS", raising=False)
    ok, message = kiosk_mcp.validate_claude_json_mcp_profile()
    assert ok is False
    assert "loads ALL" in message
