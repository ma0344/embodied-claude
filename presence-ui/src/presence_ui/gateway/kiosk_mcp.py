"""IBF-4: verify kiosk/native chat uses minimal MCP servers in settings.local.json."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from presence_ui.gateway.ccs_integration import embodied_repo_root

logger = logging.getLogger(__name__)

_DEFAULT_KIOSK_MCP = ("system-temperature",)


def expected_kiosk_mcp_servers() -> tuple[str, ...]:
    raw = os.getenv("PRESENCE_KIOSK_MCP_SERVERS", "system-temperature")
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    return tuple(parts) if parts else _DEFAULT_KIOSK_MCP


def read_enabled_mcp_servers(settings_path: Path | None = None) -> list[str] | None:
    path = settings_path or (embodied_repo_root() / ".claude" / "settings.local.json")
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    servers = data.get("enabledMcpjsonServers")
    if not isinstance(servers, list):
        return None
    return [str(item).strip() for item in servers if str(item).strip()]


def validate_kiosk_mcp_profile(*, settings_path: Path | None = None) -> tuple[bool, str]:
    """Return (ok, message). Extra MCP servers inflate LM Studio tool JSON."""
    expected = set(expected_kiosk_mcp_servers())
    actual_list = read_enabled_mcp_servers(settings_path)
    if actual_list is None:
        return False, "settings.local.json missing or has no enabledMcpjsonServers"
    actual = set(actual_list)
    if actual == expected:
        return True, f"kiosk MCP OK: {sorted(actual)}"
    extra = sorted(actual - expected)
    missing = sorted(expected - actual)
    detail_parts: list[str] = []
    if extra:
        detail_parts.append(f"extra={extra}")
    if missing:
        detail_parts.append(f"missing={missing}")
    detail = ", ".join(detail_parts)
    return (
        False,
        f"kiosk MCP mismatch ({detail}): expected {sorted(expected)}, got {sorted(actual)}",
    )


def log_kiosk_mcp_status() -> None:
    ok, message = validate_kiosk_mcp_profile()
    if ok:
        logger.info("IBF-4 %s", message)
    else:
        logger.warning("IBF-4 %s — native chat may load extra MCP tool definitions", message)
