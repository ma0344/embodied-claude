"""Export persona LoRA training JSONL from native chat sessions (RP-2a)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PRESENCE_SRC = _ROOT / "presence-ui" / "src"
if str(_PRESENCE_SRC) not in sys.path:
    sys.path.insert(0, str(_PRESENCE_SRC))

from presence_ui.training.persona_export import export_persona_jsonl, load_soul_core_text  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export ma↔こより native chat pairs for persona LoRA (RP Phase 2).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path.home() / ".claude" / "memories" / "training" / "koyori-persona.jsonl",
        help="Output JSONL path",
    )
    parser.add_argument("--max-sessions", type=int, default=40)
    parser.add_argument("--max-pairs", type=int, default=2000)
    parser.add_argument(
        "--repo",
        type=Path,
        default=_ROOT,
        help="embodied-claude repo root (for SOUL.core)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print SOUL.core size and default output path only",
    )
    args = parser.parse_args(argv)

    if args.dry_run:
        core = load_soul_core_text(repo_root=args.repo)
        print(f"SOUL.core chars: {len(core)}")
        print(f"output: {args.output}")
        return 0

    stats = export_persona_jsonl(
        repo_root=args.repo,
        output_path=args.output,
        max_sessions=args.max_sessions,
        max_pairs=args.max_pairs,
    )
    print(f"exported: {args.output}")
    print(f"sessions: {stats.sessions_scanned}")
    print(f"pairs:    {stats.pairs_written} written, {stats.pairs_skipped} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
