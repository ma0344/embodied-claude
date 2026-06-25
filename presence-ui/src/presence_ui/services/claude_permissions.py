"""Read/write Claude Code permissions.allow in settings.local.json (no secrets exposed)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from presence_ui.gateway.ccs_integration import embodied_repo_root
from presence_ui.gateway.ws_guard import (
    apply_ws_guard_to_settings,
    filter_managed_preset_ids,
    ws_guard_enabled,
)

_SETTINGS_REL = Path(".claude") / "settings.local.json"

# UI-managed presets — rules not listed here are preserved on save.
MANAGED_PRESETS: tuple[dict[str, str], ...] = (
    {"id": "web_fetch", "rule": "WebFetch", "label": "WebFetch（URL取得）"},
    {"id": "web_search", "rule": "WebSearch", "label": "WebSearch（Web検索）"},
    {"id": "wifi_cam", "rule": "mcp__wifi-cam__*", "label": "Wi-Fi カメラ（見る・聞く）"},
    {"id": "usb_webcam", "rule": "mcp__usb-webcam__*", "label": "USB ウェブカメラ"},
    {"id": "memory", "rule": "mcp__memory__*", "label": "記憶（memory）"},
    {"id": "sociality", "rule": "mcp__sociality__*", "label": "社会性（sociality）"},
    {"id": "system_temperature", "rule": "mcp__system-temperature__*", "label": "体温センサー"},
    {"id": "tts", "rule": "mcp__tts__*", "label": "声（TTS）"},
    {"id": "desire_system", "rule": "mcp__desire-system__*", "label": "欲求（desire-system）"},
)

_MANAGED_RULES = {p["rule"] for p in MANAGED_PRESETS}
_PRESET_BY_ID = {p["id"]: p for p in MANAGED_PRESETS}


def settings_local_path() -> Path:
    return embodied_repo_root() / _SETTINGS_REL


def _load_settings() -> dict[str, Any]:
    path = settings_local_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _allow_list(data: dict[str, Any]) -> list[str]:
    perms = data.get("permissions")
    if not isinstance(perms, dict):
        return []
    raw = perms.get("allow")
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


@dataclass(frozen=True)
class PermissionPresetState:
    id: str
    rule: str
    label: str
    enabled: bool


def list_permission_state() -> tuple[list[PermissionPresetState], list[str]]:
    """Return managed presets + preserved (non-UI) allow rules."""
    allow = _allow_list(_load_settings())
    allow_set = set(allow)
    guard = ws_guard_enabled()
    presets = []
    for p in MANAGED_PRESETS:
        enabled = p["rule"] in allow_set
        if guard and p["id"] in ("web_search", "web_fetch"):
            enabled = False
        presets.append(
            PermissionPresetState(
                id=p["id"],
                rule=p["rule"],
                label=p["label"],
                enabled=enabled,
            )
        )
    preserved = [r for r in allow if r not in _MANAGED_RULES]
    return presets, preserved


def save_enabled_preset_ids(enabled_ids: list[str]) -> list[str]:
    """Update settings.local.json allow list; returns final allow list."""
    enabled_ids = filter_managed_preset_ids(enabled_ids)
    unknown = [i for i in enabled_ids if i not in _PRESET_BY_ID]
    if unknown:
        raise ValueError(f"unknown preset id(s): {', '.join(unknown)}")

    data = _load_settings()
    current = _allow_list(data)
    preserved = [r for r in current if r not in _MANAGED_RULES]
    enabled_rules = [_PRESET_BY_ID[i]["rule"] for i in enabled_ids]
    new_allow = preserved + enabled_rules

    perms = data.setdefault("permissions", {})
    if not isinstance(perms, dict):
        perms = {}
        data["permissions"] = perms
    perms["allow"] = new_allow
    apply_ws_guard_to_settings(data)

    path = settings_local_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return new_allow
