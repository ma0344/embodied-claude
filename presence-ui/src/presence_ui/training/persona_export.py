"""RP Phase 2 — export native chat turns for persona LoRA training JSONL."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from presence_ui.gateway.user_prompt import looks_like_injected_prompt, strip_enriched_user_prompt
from presence_ui.services.native_session_prefs import load_hidden_session_ids
from presence_ui.services.session_log import (
    _find_project_dir,
    _messages_from_jsonl,
    get_claude_home,
    get_project_path,
    list_project_jsonl_files,
)

_KEIGO_MARKERS = ("です", "ます", "でしょうか", "ござい", "いただけ", "お役に")
_TOOL_MARKERS = ("mcp__", "gateway_turn_context", "appendSystemPrompt")
_TRIVIAL_USER_EXACT = frozenset(
    {
        "ok",
        "okay",
        "うん",
        "はい",
        "了解",
        "りょ",
        "ありがと",
        "ありがとう",
        "こんにちは",
        "こんばんは",
        "おはよう",
    }
)


@dataclass(frozen=True, slots=True)
class PersonaExportStats:
    sessions_scanned: int
    pairs_written: int
    pairs_skipped: int


def load_soul_core_text(*, repo_root: Path) -> str:
    path = repo_root / "presets" / "koyori-SOUL.core.md"
    if not path.is_file():
        raise FileNotFoundError(f"Missing SOUL.core: {path}")
    return path.read_text(encoding="utf-8").strip()


def _has_keigo(text: str) -> bool:
    return any(marker in text for marker in _KEIGO_MARKERS)


def _has_tool_markers(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _TOOL_MARKERS)


def _is_trivial_user(text: str) -> bool:
    body = re.sub(r"[!！。…~\s]+$", "", text.strip().lower())
    return body in _TRIVIAL_USER_EXACT


def _assistant_usable(text: str) -> bool:
    body = (text or "").strip()
    if len(body) < 2:
        return False
    if _has_tool_markers(body):
        return False
    if _has_keigo(body) and "うち" not in body[:40]:
        return False
    return True


def _user_usable(text: str) -> bool:
    body = strip_enriched_user_prompt(text).strip()
    if len(body) < 2:
        return False
    if looks_like_injected_prompt(body):
        return False
    if _is_trivial_user(body):
        return False
    return True


def pairs_from_session_jsonl(path: Path) -> list[tuple[str, str]]:
    messages = _messages_from_jsonl(path, strip_user_injection=True)
    pairs: list[tuple[str, str]] = []
    pending_user: str | None = None
    for msg in messages:
        if msg.sender == "ma":
            pending_user = msg.message.strip()
        elif msg.sender == "koyori" and pending_user:
            pairs.append((pending_user, msg.message.strip()))
            pending_user = None
    return pairs


def export_persona_jsonl(
    *,
    repo_root: Path,
    output_path: Path,
    project_path: str | None = None,
    max_sessions: int = 40,
    max_pairs: int = 2000,
    system_text: str | None = None,
) -> PersonaExportStats:
    system = system_text if system_text is not None else load_soul_core_text(repo_root=repo_root)
    claude_home = get_claude_home()
    project = get_project_path(project_path or str(repo_root))
    project_dir = _find_project_dir(claude_home, project)
    if project_dir is None:
        raise FileNotFoundError(f"No Claude project dir for {project!r}")

    hidden = load_hidden_session_ids()
    rows = list_project_jsonl_files(project_path=project, limit=max_sessions)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    skipped = 0
    sessions_scanned = 0

    with output_path.open("w", encoding="utf-8") as out:
        for row in rows:
            if written >= max_pairs:
                break
            session_id = str(row.get("session_file_id") or "")
            if not session_id or session_id in hidden:
                continue
            path = Path(str(row.get("path") or ""))
            if not path.is_file():
                continue
            sessions_scanned += 1
            for user_text, assistant_text in pairs_from_session_jsonl(path):
                if written >= max_pairs:
                    break
                if not _user_usable(user_text) or not _assistant_usable(assistant_text):
                    skipped += 1
                    continue
                record = {
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_text},
                        {"role": "assistant", "content": assistant_text},
                    ]
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                written += 1

    return PersonaExportStats(
        sessions_scanned=sessions_scanned,
        pairs_written=written,
        pairs_skipped=skipped,
    )
