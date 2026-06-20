"""RP Phase 2 — export native chat turns for persona LoRA training JSONL."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from presence_ui.gateway.user_prompt import (
    looks_like_agent_slash_command,
    looks_like_injected_prompt,
    strip_enriched_user_prompt,
)
from presence_ui.services.native_session_prefs import load_hidden_session_ids
from presence_ui.services.session_log import (
    _find_project_dir,
    _messages_from_jsonl,
    get_claude_home,
    get_project_path,
    list_project_jsonl_files,
)

_ASSISTANT_REJECT_EXACT = frozenset(
    {
        "no response requested.",
        "no response needed.",
        "(no response)",
    }
)
_KEIGO_MARKERS = ("です", "ます", "でしょうか", "ござい", "いただけ", "お役に")
_TOOL_MARKERS = ("mcp__", "gateway_turn_context", "appendSystemPrompt")
_PERFORMANCE_TEST_USER_MARKERS = (
    "言ってみて",
    "言ってみ",
    "もう一回",
    "もう1回",
    "もう一度",
    "読んでみて",
    "唱えて",
    "声出して",
    "リピート",
)
_PROCEDURE_ASSISTANT_MARKERS = (
    "もう一回言った",
    "言ったで",
    "言ったよ",
    "言えた",
    "試したで",
    "試してみた",
    "聞こえた",
    "送った",
    "再生した",
)
_META_PAREN_RE = re.compile(r"^[（(].*[）)]$")
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
class PersonaTrainingExample:
    system: str
    user: str
    assistant: str
    line_no: int


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


def _normalize_pair_text(text: str) -> str:
    body = re.sub(r"\s+", "", (text or "").strip())
    body = body.replace("よ！", "で！").replace("よ?", "で?")
    body = body.replace("！", "").replace("!", "").replace("？", "").replace("?", "")
    return body


def _text_tokens(text: str) -> frozenset[str]:
    normalized = _normalize_pair_text(text)
    return frozenset(re.findall(r"[\u4e00-\u9fff]{2,}", normalized)[:24])


def _texts_near_duplicate(a: str, b: str, *, threshold: float = 0.72) -> bool:
    left, right = _text_tokens(a), _text_tokens(b)
    if not left or not right:
        return _normalize_pair_text(a) == _normalize_pair_text(b)
    return len(left & right) / min(len(left), len(right)) >= threshold


def _is_meta_parenthetical_only(text: str) -> bool:
    body = (text or "").strip()
    return bool(_META_PAREN_RE.match(body)) and len(body) <= 200


def _user_is_performance_test_request(text: str) -> bool:
    return any(marker in text for marker in _PERFORMANCE_TEST_USER_MARKERS)


def _assistant_is_procedure_report(text: str) -> bool:
    if _is_meta_parenthetical_only(text):
        return True
    body = (text or "").strip()
    if len(body) > 100:
        return False
    if body.startswith("（") and "）" in body[:40]:
        return True
    return any(marker in body for marker in _PROCEDURE_ASSISTANT_MARKERS) and len(body) < 90


def pair_usable_for_training(user: str, assistant: str) -> bool:
    """Per-pair quality gate before near-duplicate clustering."""
    if not _user_usable(user) or not _assistant_usable(assistant):
        return False
    if _user_is_performance_test_request(user):
        return False
    if _assistant_is_procedure_report(assistant):
        return False
    return True


def filter_drop_all_near_duplicate_pairs(
    pairs: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Drop every pair in a near-duplicate cluster (keep only singletons)."""
    if len(pairs) <= 1:
        return list(pairs)

    parent = list(range(len(pairs)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for i in range(len(pairs)):
        user_i, assistant_i = pairs[i]
        for j in range(i + 1, len(pairs)):
            user_j, assistant_j = pairs[j]
            exact_pair = (
                _normalize_pair_text(user_i) == _normalize_pair_text(user_j)
                and _normalize_pair_text(assistant_i) == _normalize_pair_text(assistant_j)
            )
            if exact_pair or _texts_near_duplicate(assistant_i, assistant_j):
                union(i, j)

    groups: dict[int, list[int]] = {}
    for index in range(len(pairs)):
        groups.setdefault(find(index), []).append(index)

    kept: list[tuple[str, str]] = []
    for members in groups.values():
        if len(members) == 1:
            kept.append(pairs[members[0]])
    return kept


def _assistant_usable(text: str) -> bool:
    body = (text or "").strip()
    if len(body) < 2:
        return False
    if body.lower() in _ASSISTANT_REJECT_EXACT:
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
    if looks_like_agent_slash_command(body):
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
    candidates: list[tuple[str, str]] = []

    for row in rows:
        session_id = str(row.get("session_file_id") or "")
        if not session_id or session_id in hidden:
            continue
        path = Path(str(row.get("path") or ""))
        if not path.is_file():
            continue
        sessions_scanned += 1
        for user_text, assistant_text in pairs_from_session_jsonl(path):
            if pair_usable_for_training(user_text, assistant_text):
                candidates.append((user_text, assistant_text))
            else:
                skipped += 1

    filtered = filter_drop_all_near_duplicate_pairs(candidates)
    skipped += len(candidates) - len(filtered)

    with output_path.open("w", encoding="utf-8") as out:
        for user_text, assistant_text in filtered[:max_pairs]:
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


def _message_content(messages: list[dict[str, str]], role: str) -> str:
    for item in messages:
        if str(item.get("role") or "") == role:
            return str(item.get("content") or "").strip()
    return ""


def load_persona_jsonl(path: Path) -> list[PersonaTrainingExample]:
    """Load training JSONL produced by export_persona_jsonl."""
    if not path.is_file():
        raise FileNotFoundError(f"Missing training JSONL: {path}")

    examples: list[PersonaTrainingExample] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            messages = record.get("messages")
            if not isinstance(messages, list):
                raise ValueError(f"{path}:{line_no}: missing messages[]")
            examples.append(
                PersonaTrainingExample(
                    system=_message_content(messages, "system"),
                    user=_message_content(messages, "user"),
                    assistant=_message_content(messages, "assistant"),
                    line_no=line_no,
                )
            )
    return examples


def format_persona_markdown(
    examples: list[PersonaTrainingExample],
    *,
    source_path: Path | None = None,
    show_full_system: bool = False,
    system_preview_chars: int = 320,
) -> str:
    """Human-readable Markdown review for LoRA training pairs."""
    source = str(source_path) if source_path else "(unknown)"
    lines = [
        "# Koyori persona training preview",
        "",
        f"- source: `{source}`",
        f"- pairs: {len(examples)}",
        "",
        "---",
        "",
    ]

    system_text = examples[0].system if examples else ""
    if system_text:
        lines.extend(["## System (SOUL.core)", ""])
        if show_full_system:
            lines.append(system_text)
        else:
            preview = system_text[:system_preview_chars]
            if len(system_text) > system_preview_chars:
                preview += "…"
            lines.append(preview)
            lines.append("")
            lines.append(
                f"_({len(system_text)} chars total — use `--full-system` to show all)_"
            )
        lines.extend(["", "---", ""])

    for index, example in enumerate(examples, start=1):
        lines.extend(
            [
                f"## Pair {index} · line {example.line_no}",
                "",
                "### まー",
                "",
                example.user,
                "",
                "### こより",
                "",
                example.assistant,
                "",
                "---",
                "",
            ]
        )

    if not examples:
        lines.append("_No training pairs in file._")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
