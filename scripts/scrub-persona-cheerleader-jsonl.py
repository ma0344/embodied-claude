"""Scrub cheerleader closings from existing persona LoRA JSONL files.

Run from repo (uses presence-ui venv — required for imports):
  cd presence-ui
  uv run python ..\\scripts\\scrub-persona-cheerleader-jsonl.py
  uv run python ..\\scripts\\scrub-persona-cheerleader-jsonl.py --apply
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from presence_ui.training.cheerleader_strip import strip_trailing_cheerleader_closings

DEFAULT_DIR = Path.home() / ".claude" / "memories" / "training"
DEFAULT_PATHS = (
    DEFAULT_DIR / "koyori-persona-candidates.jsonl",
    DEFAULT_DIR / "koyori-persona.jsonl",
)


def _scrub_file(path: Path, *, apply: bool) -> tuple[int, int, int]:
    if not path.is_file():
        return 0, 0, 0
    lines = path.read_text(encoding="utf-8").splitlines()
    changed = 0
    emptied = 0
    out_lines: list[str] = []
    for raw in lines:
        if not raw.strip():
            continue
        record = json.loads(raw)
        messages = record.get("messages")
        if not isinstance(messages, list):
            out_lines.append(raw)
            continue
        touched = False
        for msg in messages:
            if str(msg.get("role") or "") != "assistant":
                continue
            before = str(msg.get("content") or "")
            after = strip_trailing_cheerleader_closings(before)
            if after != before:
                msg["content"] = after
                touched = True
            if not after.strip():
                emptied += 1
        if touched:
            changed += 1
        if any(
            str(m.get("role") or "") == "assistant" and str(m.get("content") or "").strip()
            for m in messages
        ):
            out_lines.append(json.dumps(record, ensure_ascii=False))

    if apply and (changed or len(out_lines) < len([line for line in lines if line.strip()])):
        backup = path.with_suffix(path.suffix + ".bak")
        if not backup.is_file():
            shutil.copy2(path, backup)
        path.write_text("\n".join(out_lines) + ("\n" if out_lines else ""), encoding="utf-8")
    return len(out_lines), changed, emptied


def main() -> int:
    parser = argparse.ArgumentParser(description="Strip cheerleader closings from persona JSONL")
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    parser.add_argument(
        "--path",
        type=Path,
        action="append",
        help="JSONL file (default: candidates + curated)",
    )
    args = parser.parse_args()

    paths = args.path or list(DEFAULT_PATHS)
    total_changed = 0
    total_emptied = 0
    for path in paths:
        total, changed, emptied = _scrub_file(path, apply=args.apply)
        print(f"{path}: {total} pairs kept, {changed} trimmed, {emptied} emptied (dropped)")
        total_changed += changed
        total_emptied += emptied

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to write (.bak backup on first apply).")
    else:
        print(f"\nApplied: trimmed {total_changed} lines, dropped {total_emptied} empty assistants.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
