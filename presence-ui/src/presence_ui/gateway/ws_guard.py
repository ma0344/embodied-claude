"""WS-1/WS-3 — block CC WebSearch/WebFetch; honest citations until gateway prefetch (WS-2)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

CC_WEB_TOOL_RULES: tuple[str, ...] = ("WebSearch", "WebFetch")

_WEB_SEARCH_CUE = re.compile(
    r"(調べて|調べてもら|検索して|ネットで|オンラインで|"
    r"どこにある|見つけて|探して|ググって|"
    r"\bsearch\b|\blook\s+up\b|webで)",
    re.IGNORECASE,
)

_WS_STABLE_APPEND = """[Web lookup — WS guard]
Do NOT call WebSearch or WebFetch in this chat. Gateway will inject
[web_search_prefetch] or [url_prefetch] when search results are available.
Never add a Sources: section or fabricate URLs/citations.
If you have no prefetch evidence, say honestly that you could not verify online."""


def ws_guard_enabled() -> bool:
    raw = os.getenv("PRESENCE_WS_GUARD", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def ws_guard_stable_append() -> str:
    return _WS_STABLE_APPEND if ws_guard_enabled() else ""


def looks_like_web_search_request(text: str) -> bool:
    line = (text or "").strip()
    if not line or len(line) > 500:
        return False
    return bool(_WEB_SEARCH_CUE.search(line))


def web_search_honesty_directive() -> str:
    return (
        "[Gateway directive — not for the user]\n"
        "Web lookup via Claude tools is disabled. Do NOT call WebSearch/WebFetch. "
        "Do NOT invent Sources, URLs, or page contents. "
        "Tell まー honestly if you cannot verify online yet; ask for a direct URL if needed."
    )


def _repo_root() -> Path:
    from presence_ui.gateway.ccs_integration import embodied_repo_root

    return embodied_repo_root()


def _settings_path() -> Path:
    return _repo_root() / ".claude" / "settings.local.json"


def _load_settings(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def apply_ws_guard_to_settings(data: dict) -> bool:
    """Remove WebSearch/WebFetch from allow; ensure permissions.deny lists them."""
    if not ws_guard_enabled():
        return False
    perms = data.setdefault("permissions", {})
    if not isinstance(perms, dict):
        perms = {}
        data["permissions"] = perms

    allow_raw = perms.get("allow")
    allow = [str(x).strip() for x in allow_raw] if isinstance(allow_raw, list) else []
    deny_raw = perms.get("deny")
    deny = [str(x).strip() for x in deny_raw] if isinstance(deny_raw, list) else []

    modified = False
    blocked = set(CC_WEB_TOOL_RULES)
    new_allow = [rule for rule in allow if rule not in blocked]
    if new_allow != allow:
        allow = new_allow
        modified = True

    deny_set = set(deny)
    for rule in CC_WEB_TOOL_RULES:
        if rule not in deny_set:
            deny.append(rule)
            deny_set.add(rule)
            modified = True

    perms["allow"] = allow
    perms["deny"] = deny
    return modified


def ensure_ws_guard_permissions(*, write: bool = True) -> bool:
    """Sync settings.local.json for WS-3. Returns True if file was updated."""
    if not ws_guard_enabled():
        return False
    path = _settings_path()
    data = _load_settings(path)
    if not apply_ws_guard_to_settings(data):
        return False
    if not write:
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def filter_managed_preset_ids(enabled_ids: list[str]) -> list[str]:
    if not ws_guard_enabled():
        return enabled_ids
    blocked = {"web_search", "web_fetch"}
    return [item for item in enabled_ids if item not in blocked]
