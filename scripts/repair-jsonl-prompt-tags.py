"""Repair orphaned [stm_recent] / [dream_digest] tags in native chat JSONL logs.

Usage:
  uv run python scripts/repair-jsonl-prompt-tags.py          # dry-run
  uv run python scripts/repair-jsonl-prompt-tags.py --apply  # write fixes
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

# Repo root on sys.path when invoked from scripts/
_ROOT = Path(__file__).resolve().parents[1]
_PRESENCE_SRC = _ROOT / "presence-ui" / "src"
if str(_PRESENCE_SRC) not in sys.path:
    sys.path.insert(0, str(_PRESENCE_SRC))

from presence_ui.gateway.prompt_block_safe import (  # noqa: E402
    has_unclosed_paired_tags,
    repair_enriched_user_prompt,
)
from presence_ui.services.session_log import get_claude_home, get_project_path  # noqa: E402
from presence_ui.services.native_history import resolve_session_jsonl_path  # noqa: E402


def _user_text_from_record(record: dict) -> str | None:
    if (record.get("type") or record.get("role")) != "user":
        return None
    message = record.get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = str(block.get("text") or "").strip()
                if text:
                    parts.append(text)
        return "\n".join(parts) if parts else None
    return None


def _set_user_text(record: dict, text: str) -> None:
    message = record.setdefault("message", {})
    content = message.get("content")
    if isinstance(content, str):
        message["content"] = text
        return
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                block["text"] = text
                return
    message["content"] = text


def repair_jsonl_file(path: Path, *, apply: bool) -> int:
    if not path.is_file():
        return 0
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    changed = 0
    out_lines: list[str] = []
    for line in raw_lines:
        if not line.strip():
            out_lines.append(line)
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            out_lines.append(line)
            continue
        text = _user_text_from_record(record)
        if text and has_unclosed_paired_tags(text):
            fixed = repair_enriched_user_prompt(text)
            if fixed != text:
                changed += 1
                _set_user_text(record, fixed)
                line = json.dumps(record, ensure_ascii=False)
        out_lines.append(line)

    if changed and apply:
        backup = path.with_suffix(path.suffix + ".bak")
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text("\n".join(out_lines) + ("\n" if out_lines else ""), encoding="utf-8")
    return changed


def iter_jsonl_files(project_path: str | None = None) -> list[Path]:
    claude_home = get_claude_home()
    project = get_project_path(project_path)
    encoded = "".join("-" if ch in (":", "\\", "/") else ch for ch in __import__("os").path.normpath(project))
    project_dir = claude_home / "projects" / encoded
    if not project_dir.is_dir():
        return []
    return sorted(project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair unclosed STM/dream tags in JSONL user prompts")
    parser.add_argument("--apply", action="store_true", help="Write repaired JSONL (creates .jsonl.bak once)")
    parser.add_argument("--session-id", help="Repair a single session id only")
    args = parser.parse_args()

    files: list[Path]
    if args.session_id:
        path = resolve_session_jsonl_path(args.session_id)
        if path is None:
            print(f"session not found: {args.session_id}", file=sys.stderr)
            return 1
        files = [path]
    else:
        files = iter_jsonl_files()

    total_files = 0
    total_records = 0
    for path in files:
        n = repair_jsonl_file(path, apply=args.apply)
        if n:
            total_files += 1
            total_records += n
            mode = "fixed" if args.apply else "would fix"
            print(f"{mode}: {path.name} ({n} user record(s))")

    verb = "Repaired" if args.apply else "Would repair"
    print(f"{verb} {total_records} user record(s) in {total_files} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
