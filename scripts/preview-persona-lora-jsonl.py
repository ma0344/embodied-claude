"""Render persona LoRA training JSONL as readable Markdown."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PRESENCE_SRC = _ROOT / "presence-ui" / "src"
if str(_PRESENCE_SRC) not in sys.path:
    sys.path.insert(0, str(_PRESENCE_SRC))

from presence_ui.training.persona_export import (  # noqa: E402
    format_persona_markdown,
    load_persona_jsonl,
)

_DEFAULT_JSONL = Path.home() / ".claude" / "memories" / "training" / "koyori-persona.jsonl"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preview koyori-persona.jsonl as readable Markdown.",
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=_DEFAULT_JSONL,
        help="Training JSONL path",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write Markdown here (default: stdout, or input path with .md)",
    )
    parser.add_argument(
        "--full-system",
        action="store_true",
        help="Include full SOUL.core system block (default: preview only)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Preview first N pairs only (0 = all)",
    )
    args = parser.parse_args(argv)

    examples = load_persona_jsonl(args.input)
    if args.limit > 0:
        examples = examples[: args.limit]

    markdown = format_persona_markdown(
        examples,
        source_path=args.input,
        show_full_system=args.full_system,
    )

    if args.output:
        out_path = args.output
    elif args.input.suffix.lower() == ".jsonl":
        out_path = args.input.with_suffix(".md")
    else:
        out_path = None

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(markdown, encoding="utf-8")
        print(f"preview: {out_path}")
        print(f"pairs:   {len(examples)}")
    else:
        sys.stdout.write(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
