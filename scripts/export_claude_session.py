#!/usr/bin/env python3
"""Export Claude Code session JSONL logs to editable Markdown."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def default_project_path() -> str:
    env = os.environ.get("PRESENCE_PROJECT_PATH")
    if env:
        return str(Path(env).expanduser().resolve())
    return str(Path.cwd().resolve())


def encode_project_path(project_path: str) -> str:
    normalized = os.path.normpath(project_path)
    return "".join("-" if ch in (":", "\\", "/") else ch for ch in normalized)


def find_project_dir(claude_home: Path, project_path: str) -> Path:
    projects_root = claude_home / "projects"
    encoded = encode_project_path(project_path)
    if not projects_root.is_dir():
        raise FileNotFoundError(f"Claude projects dir not found: {projects_root}")

    exact = projects_root / encoded
    if exact.is_dir():
        return exact

    lowered = encoded.lower()
    for child in projects_root.iterdir():
        if child.is_dir() and child.name.lower() == lowered:
            return child

    raise FileNotFoundError(
        f"No Claude project dir for {project_path!r} "
        f"(expected {projects_root / encoded})"
    )


def load_history_index(claude_home: Path, project_path: str) -> dict[str, dict[str, Any]]:
    history_file = claude_home / "history.jsonl"
    if not history_file.is_file():
        return {}

    project_norm = os.path.normcase(os.path.normpath(project_path))
    index: dict[str, dict[str, Any]] = {}
    with history_file.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if os.path.normcase(os.path.normpath(row.get("project", ""))) != project_norm:
                continue
            session_id = row.get("sessionId")
            if not session_id:
                continue
            entry = index.setdefault(
                session_id,
                {"last_display": "", "last_timestamp": 0, "first_display": ""},
            )
            display = (row.get("display") or "").strip()
            ts = int(row.get("timestamp") or 0)
            if display and not entry["first_display"]:
                entry["first_display"] = display
            if display and ts >= entry["last_timestamp"]:
                entry["last_display"] = display
                entry["last_timestamp"] = ts
    return index


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return records


def _content_blocks_to_text(content: Any) -> list[tuple[str, str]]:
    """Return (kind, text) pairs from a message content field."""
    if isinstance(content, str):
        text = content.strip()
        return [("prompt", text)] if text else []

    if not isinstance(content, list):
        return []

    parts: list[tuple[str, str]] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type", "unknown")
        if block_type == "text":
            text = (block.get("text") or "").strip()
            if text:
                parts.append(("prompt", text))
        elif block_type == "tool_result":
            text = _tool_result_to_text(block)
            parts.append(("tool_result", text))
        elif block_type == "thinking":
            text = (block.get("thinking") or "").strip()
            if text:
                parts.append(("thinking", text))
        elif block_type == "tool_use":
            name = block.get("name", "tool")
            payload = json.dumps(block.get("input", {}), ensure_ascii=False, indent=2)
            parts.append(("tool_use", f"{name}\n{payload}"))
        else:
            payload = json.dumps(block, ensure_ascii=False, indent=2)
            parts.append((block_type, payload))
    return parts


def _tool_result_to_text(block: dict[str, Any]) -> str:
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(str(item.get("text", "")))
            else:
                texts.append(json.dumps(item, ensure_ascii=False))
        return "\n".join(texts)
    if block.get("is_error"):
        return f"[error] {content}"
    return json.dumps(content, ensure_ascii=False, indent=2)


def classify_user_record(record: dict[str, Any]) -> str:
    message = record.get("message") or {}
    parts = _content_blocks_to_text(message.get("content"))
    kinds = {kind for kind, _ in parts}
    if "prompt" in kinds:
        return "user · prompt"
    if "tool_result" in kinds:
        return "user · tool_result"
    return "user"


def classify_assistant_record(record: dict[str, Any]) -> str:
    message = record.get("message") or {}
    parts = _content_blocks_to_text(message.get("content"))
    kinds = {kind for kind, _ in parts}
    if kinds == {"thinking"}:
        return "assistant · thinking"
    if "tool_use" in kinds and "text" not in kinds and "thinking" not in kinds:
        return "assistant · tool_use"
    if kinds <= {"text"} and parts:
        return "assistant · reply"
    return "assistant"


def format_record_body(record: dict[str, Any]) -> str:
    rec_type = record.get("type", "unknown")

    if rec_type == "user":
        parts = _content_blocks_to_text((record.get("message") or {}).get("content"))
        if not parts:
            return "_empty user message_"
        chunks: list[str] = []
        for kind, text in parts:
            if kind == "prompt":
                chunks.append(text)
            else:
                chunks.append(f"**[{kind}]**\n\n```\n{text}\n```")
        return "\n\n".join(chunks)

    if rec_type == "assistant":
        parts = _content_blocks_to_text((record.get("message") or {}).get("content"))
        if not parts:
            return "_empty assistant message_"
        chunks = []
        for kind, text in parts:
            label = kind if kind != "prompt" else "text"
            chunks.append(f"**[{label}]**\n\n{text}" if kind != "text" else text)
        return "\n\n".join(chunks)

    if rec_type == "attachment":
        attachment = record.get("attachment") or {}
        att_type = attachment.get("type", "attachment")
        content = attachment.get("content") or attachment.get("stdout") or ""
        if isinstance(content, (dict, list)):
            content = json.dumps(content, ensure_ascii=False, indent=2)
        return f"**attachment:{att_type}**\n\n```\n{content}\n```"

    if rec_type == "system":
        subtype = record.get("subtype", "system")
        content = record.get("content")
        if content:
            return f"**system:{subtype}**\n\n{content}"
        payload = {k: v for k, v in record.items() if k not in {"type", "subtype", "uuid", "parentUuid"}}
        return f"**system:{subtype}**\n\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"

    if rec_type == "ai-title":
        return f"**title:** {record.get('aiTitle', '')}"

    if rec_type in {"permission-mode", "file-history-snapshot"}:
        return f"```json\n{json.dumps(record, ensure_ascii=False, indent=2)}\n```"

    return f"```json\n{json.dumps(record, ensure_ascii=False, indent=2)}\n```"


@dataclass
class SessionSummary:
    session_id: str
    jsonl_path: Path
    mtime: float
    ai_title: str = ""
    first_user_prompt: str = ""
    last_user_prompt: str = ""
    user_prompt_count: int = 0
    record_count: int = 0
    history_last_display: str = ""
    history_first_display: str = ""


def summarize_session(path: Path, history: dict[str, dict[str, Any]] | None = None) -> SessionSummary:
    session_id = path.stem
    summary = SessionSummary(
        session_id=session_id,
        jsonl_path=path,
        mtime=path.stat().st_mtime,
    )
    if history and session_id in history:
        row = history[session_id]
        summary.history_first_display = row.get("first_display", "")
        summary.history_last_display = row.get("last_display", "")

    for record in read_jsonl(path):
        summary.record_count += 1
        if record.get("type") == "ai-title":
            summary.ai_title = record.get("aiTitle") or summary.ai_title
            continue
        if record.get("type") != "user":
            continue
        parts = _content_blocks_to_text((record.get("message") or {}).get("content"))
        prompts = [text for kind, text in parts if kind == "prompt"]
        if not prompts:
            continue
        text = "\n".join(prompts)
        summary.user_prompt_count += 1
        if not summary.first_user_prompt:
            summary.first_user_prompt = text
        summary.last_user_prompt = text

    return summary


def list_sessions(project_dir: Path, history: dict[str, dict[str, Any]]) -> list[SessionSummary]:
    sessions = [
        summarize_session(path, history)
        for path in sorted(project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    ]
    return sessions


def resolve_session_path(
    project_dir: Path,
    session_id: str | None,
    latest: bool,
) -> Path:
    files = sorted(project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError(f"No session JSONL files in {project_dir}")

    if latest or not session_id:
        return files[0]

    sid = session_id.lower()
    matches = [p for p in files if p.stem.lower() == sid or p.stem.lower().startswith(sid)]
    if not matches:
        raise FileNotFoundError(
            f"No session matching {session_id!r} in {project_dir}. Run --list."
        )
    if len(matches) > 1:
        ids = ", ".join(p.stem for p in matches)
        raise ValueError(f"Session id prefix {session_id!r} is ambiguous: {ids}")
    return matches[0]


def build_dialogue_section(records: list[dict[str, Any]]) -> str:
    lines = ["## Dialogue (user prompts + assistant replies)", ""]
    turn = 0
    for record in records:
        rec_type = record.get("type")
        ts = record.get("timestamp", "")
        if rec_type == "user":
            parts = _content_blocks_to_text((record.get("message") or {}).get("content"))
            prompts = [text for kind, text in parts if kind == "prompt"]
            if not prompts:
                continue
            turn += 1
            lines.append(f"### Turn {turn} · まー · {ts}")
            lines.append("")
            lines.append("\n".join(prompts))
            lines.append("")
        elif rec_type == "assistant":
            parts = _content_blocks_to_text((record.get("message") or {}).get("content"))
            replies = [text for kind, text in parts if kind in {"text", "prompt"}]
            if not replies:
                continue
            lines.append(f"### Turn {turn} · こより · {ts}")
            lines.append("")
            lines.append("\n".join(replies))
            lines.append("")
    if turn == 0:
        lines.append("_No user prompts found._")
        lines.append("")
    return "\n".join(lines)


def build_full_section(records: list[dict[str, Any]]) -> str:
    lines = ["## Full log (all JSONL records)", ""]
    for index, record in enumerate(records, start=1):
        rec_type = record.get("type", "unknown")
        ts = record.get("timestamp", "")
        uuid = record.get("uuid", "")

        if rec_type == "user":
            label = classify_user_record(record)
        elif rec_type == "assistant":
            label = classify_assistant_record(record)
        elif rec_type == "system":
            label = f"system · {record.get('subtype', 'event')}"
        elif rec_type == "attachment":
            label = f"attachment · {(record.get('attachment') or {}).get('type', 'unknown')}"
        else:
            label = rec_type

        lines.append(f"### {index:04d} · {label} · {ts}")
        if uuid:
            lines.append(f"_uuid: {uuid}_")
        lines.append("")
        lines.append(format_record_body(record))
        lines.append("")
    return "\n".join(lines)


def export_session_markdown(
    *,
    project_path: str,
    jsonl_path: Path,
    records: list[dict[str, Any]],
    summary: SessionSummary,
) -> str:
    exported_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    title = summary.ai_title or summary.history_last_display or summary.first_user_prompt[:60]
    header = [
        f"# Claude Code session export",
        "",
        f"**{title}**",
        "",
        "| | |",
        "|---|---|",
        f"| session_id | `{summary.session_id}` |",
        f"| project | `{project_path}` |",
        f"| source_jsonl | `{jsonl_path}` |",
        f"| exported_at | {exported_at} |",
        f"| records | {len(records)} |",
        f"| user_prompts | {summary.user_prompt_count} |",
        "",
        "編集用: 下の **Full log** が JSONL の全行に対応。会話だけ見るなら **Dialogue**。",
        "",
        "---",
        "",
    ]
    return "\n".join(header) + build_dialogue_section(records) + "\n---\n\n" + build_full_section(records)


def print_session_table(sessions: list[SessionSummary], project_path: str, project_dir: Path) -> None:
    print(f"project: {project_path}")
    print(f"dir:     {project_dir}")
    print("")
    if not sessions:
        print("No sessions.")
        return
    print(f"{'#':<3} {'session_id':<38} {'updated':<20} {'prompts':>7}  title / last prompt")
    print("-" * 110)
    for i, s in enumerate(sessions, start=1):
        updated = datetime.fromtimestamp(s.mtime).strftime("%Y-%m-%d %H:%M")
        title = s.ai_title or s.history_last_display or s.last_user_prompt or s.first_user_prompt
        title = re.sub(r"\s+", " ", title).strip()
        if len(title) > 48:
            title = title[:45] + "..."
        marker = "*" if i == 1 else " "
        print(f"{marker}{i:<2} {s.session_id:<38} {updated:<20} {s.user_prompt_count:>7}  {title}")


def default_output_path(output_dir: Path, summary: SessionSummary) -> Path:
    stamp = datetime.fromtimestamp(summary.mtime).strftime("%Y%m%d-%H%M")
    short_id = summary.session_id[:8]
    slug = summary.ai_title or summary.history_last_display or "session"
    slug = re.sub(r"[^\w\u3040-\u30ff\u4e00-\u9fff-]+", "-", slug.lower()).strip("-")
    slug = slug[:40] or "session"
    return output_dir / f"{stamp}-{short_id}-{slug}.md"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export Claude Code ~/.claude/projects JSONL session logs to Markdown.",
    )
    parser.add_argument(
        "--claude-home",
        default=os.environ.get("CLAUDE_HOME", str(Path.home() / ".claude")),
        help="Claude config home (default: ~/.claude)",
    )
    parser.add_argument(
        "--project",
        default=default_project_path(),
        help="Project path (default: PRESENCE_PROJECT_PATH or current directory)",
    )
    parser.add_argument("--list", action="store_true", help="List sessions for the project")
    parser.add_argument("--session-id", help="Session UUID or unique prefix")
    parser.add_argument("--latest", action="store_true", help="Export newest session (default)")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output .md path (default: ~/.claude/memories/session-exports/)",
    )
    args = parser.parse_args(argv)

    claude_home = Path(args.claude_home).expanduser()
    project_path = str(Path(args.project).resolve())
    project_dir = find_project_dir(claude_home, project_path)
    history = load_history_index(claude_home, project_path)

    if args.list:
        sessions = list_sessions(project_dir, history)
        print_session_table(sessions, project_path, project_dir)
        print("")
        print("* = newest (default for export without --session-id)")
        print("")
        print("Specify session:")
        print("  --session-id <full-uuid>")
        print("  --session-id <prefix>   # unique prefix match")
        return 0

    jsonl_path = resolve_session_path(project_dir, args.session_id, args.latest or not args.session_id)
    records = read_jsonl(jsonl_path)
    summary = summarize_session(jsonl_path, history)

    output_dir = Path(args.output).parent if args.output else claude_home / "memories" / "session-exports"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output if args.output else default_output_path(output_dir, summary)

    markdown = export_session_markdown(
        project_path=project_path,
        jsonl_path=jsonl_path,
        records=records,
        summary=summary,
    )
    output_path.write_text(markdown, encoding="utf-8")

    print(f"exported: {output_path}")
    print(f"session:  {summary.session_id}")
    print(f"records:  {len(records)}")
    print(f"prompts:  {summary.user_prompt_count}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
