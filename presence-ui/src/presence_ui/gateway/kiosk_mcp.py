"""IBF-4: verify kiosk/native chat uses minimal MCP servers in settings.local.json."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from presence_ui.gateway.ccs_integration import embodied_repo_root

logger = logging.getLogger(__name__)

_DEFAULT_KIOSK_MCP = ("system-temperature",)
_RUNTIME_MCP_REL = Path(".claude") / "mcp-kiosk.runtime.json"


def expected_kiosk_mcp_servers() -> tuple[str, ...]:
    raw = os.getenv("PRESENCE_KIOSK_MCP_SERVERS", "system-temperature")
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    return tuple(parts) if parts else _DEFAULT_KIOSK_MCP


def strict_mcp_config_enabled() -> bool:
    """When true, native chat subprocess uses --strict-mcp-config (not settings.local alone)."""
    raw = os.getenv("PRESENCE_STRICT_MCP_CONFIG", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def settings_local_paths() -> tuple[Path, ...]:
    """Claude Code may read repo-root and .claude/ settings.local.json — keep both aligned."""
    root = embodied_repo_root()
    return (
        root / "settings.local.json",
        root / ".claude" / "settings.local.json",
    )


def claude_json_path() -> Path:
    return Path.home() / ".claude.json"


def _settings_label(path: Path) -> str:
    try:
        return str(path.relative_to(embodied_repo_root())).replace("\\", "/")
    except ValueError:
        return str(path)


def _project_keys_for_repo() -> tuple[str, ...]:
    root = embodied_repo_root().resolve()
    return (
        root.as_posix(),
        str(root),
    )


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


def read_claude_json_enabled_servers() -> list[str] | None:
    """What Claude CLI actually uses for MCP enablement (~/.claude.json project entry)."""
    path = claude_json_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    projects = data.get("projects")
    if not isinstance(projects, dict):
        return None
    for key in _project_keys_for_repo():
        entry = projects.get(key)
        if not isinstance(entry, dict):
            continue
        servers = entry.get("enabledMcpjsonServers")
        if isinstance(servers, list):
            return [str(item).strip() for item in servers if str(item).strip()]
    return None


def sync_enabled_mcp_to_claude_json() -> tuple[bool, str]:
    """Mirror settings.local.json enablement into ~/.claude.json (Claude ignores project settings)."""
    expected = list(expected_kiosk_mcp_servers())
    path = claude_json_path()
    if not path.is_file():
        return False, f"{path} not found — run `claude` once to create it"

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return False, f"failed to read {path}: {exc}"

    projects = data.setdefault("projects", {})
    if not isinstance(projects, dict):
        projects = {}
        data["projects"] = projects

    updated = False
    for key in _project_keys_for_repo():
        entry = projects.setdefault(key, {})
        if not isinstance(entry, dict):
            entry = {}
            projects[key] = entry
        current = entry.get("enabledMcpjsonServers")
        if current != expected:
            entry["enabledMcpjsonServers"] = expected
            updated = True

    if updated:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return True, f"synced ~/.claude.json enabledMcpjsonServers={expected}"

    return True, f"~/.claude.json already has enabledMcpjsonServers={expected}"


def build_strict_mcp_config_file() -> Path:
    """Write filtered .mcp.json for --strict-mcp-config (kiosk native chat subprocess)."""
    root = embodied_repo_root()
    servers = expected_kiosk_mcp_servers()
    mcp_path = root / ".mcp.json"
    if not mcp_path.is_file():
        raise FileNotFoundError(f".mcp.json not found at {mcp_path}")

    data = json.loads(mcp_path.read_text(encoding="utf-8"))
    all_servers = data.get("mcpServers")
    if not isinstance(all_servers, dict):
        raise ValueError(".mcp.json has no mcpServers object")

    missing = [name for name in servers if name not in all_servers]
    if missing:
        raise ValueError(f"MCP servers missing from .mcp.json: {missing}")

    filtered = {name: all_servers[name] for name in servers}
    out = root / _RUNTIME_MCP_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"mcpServers": filtered}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return out


def validate_kiosk_mcp_profile(*, settings_path: Path | None = None) -> tuple[bool, str]:
    """Return (ok, message). Extra MCP servers inflate LM Studio tool JSON."""
    expected = set(expected_kiosk_mcp_servers())
    paths = (settings_path,) if settings_path is not None else settings_local_paths()

    readings: list[tuple[str, set[str]]] = []
    for path in paths:
        actual_list = read_enabled_mcp_servers(path)
        if actual_list is not None:
            readings.append((_settings_label(path), set(actual_list)))

    if not readings:
        return False, "settings.local.json missing or has no enabledMcpjsonServers"

    if len(readings) > 1:
        base_label, base_servers = readings[0]
        for label, servers in readings[1:]:
            if servers != base_servers:
                return (
                    False,
                    "kiosk MCP settings disagree "
                    f"({base_label}={sorted(base_servers)} vs {label}={sorted(servers)})",
                )

    actual = readings[0][1]
    if actual == expected:
        sources = ", ".join(label for label, _ in readings)
        return True, f"kiosk MCP OK ({sources}): {sorted(actual)}"

    extra = sorted(actual - expected)
    missing = sorted(expected - actual)
    detail_parts: list[str] = []
    if extra:
        detail_parts.append(f"extra={extra}")
    if missing:
        detail_parts.append(f"missing={missing}")
    detail = ", ".join(detail_parts)
    sources = ", ".join(label for label, _ in readings)
    return (
        False,
        f"kiosk MCP mismatch ({detail}) in {sources}: "
        f"expected {sorted(expected)}, got {sorted(actual)}",
    )


def validate_claude_json_mcp_profile() -> tuple[bool, str]:
    """Claude CLI reads enablement from ~/.claude.json, not settings.local.json."""
    expected = set(expected_kiosk_mcp_servers())
    actual_list = read_claude_json_enabled_servers()
    if actual_list is None:
        return (
            False,
            "~/.claude.json has no project entry for this repo — "
            "empty enablement loads ALL .mcp.json servers",
        )
    actual = set(actual_list)
    if actual == expected:
        return True, f"~/.claude.json MCP OK: {sorted(actual)}"
    if not actual:
        return (
            False,
            "~/.claude.json enabledMcpjsonServers=[] loads ALL .mcp.json servers "
            f"(expected {sorted(expected)})",
        )
    return (
        False,
        f"~/.claude.json MCP mismatch: expected {sorted(expected)}, got {sorted(actual)}",
    )


def log_kiosk_mcp_status() -> None:
    ok, message = validate_kiosk_mcp_profile()
    if ok:
        logger.info("IBF-4 %s", message)
    else:
        logger.warning("IBF-4 %s — native chat may load extra MCP tool definitions", message)

    json_ok, json_message = validate_claude_json_mcp_profile()
    if json_ok:
        logger.info("IBF-4 %s", json_message)
    else:
        logger.warning("IBF-4 %s", json_message)

    sync_ok, sync_message = sync_enabled_mcp_to_claude_json()
    if sync_ok:
        logger.info("IBF-4 %s", sync_message)
    else:
        logger.warning("IBF-4 %s", sync_message)

    if strict_mcp_config_enabled():
        try:
            mcp_path = build_strict_mcp_config_file()
            logger.info("IBF-4 strict MCP config: %s", mcp_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("IBF-4 strict MCP config failed: %s", exc)
