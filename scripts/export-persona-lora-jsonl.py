"""Export persona LoRA training JSONL from native chat sessions (RP-2a)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PRESENCE_SRC = _ROOT / "presence-ui" / "src"
if str(_PRESENCE_SRC) not in sys.path:
    sys.path.insert(0, str(_PRESENCE_SRC))

from presence_ui.training.persona_curation import (  # noqa: E402
    apply_persona_curation,
    persona_candidates_jsonl_path,
    persona_curated_jsonl_path,
)
from presence_ui.training.persona_export import export_persona_jsonl, load_soul_core_text  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export ma↔こより native chat pairs for persona LoRA (RP Phase 2).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Candidates JSONL path (default: koyori-persona-candidates.jsonl)",
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
        help="Print SOUL.core size and default output paths only",
    )
    args = parser.parse_args(argv)

    candidates_path = args.output or persona_candidates_jsonl_path()
    curated_path = persona_curated_jsonl_path()

    if args.dry_run:
        core = load_soul_core_text(repo_root=args.repo)
        print(f"SOUL.core chars: {len(core)}")
        print(f"candidates: {candidates_path}")
        print(f"curated:    {curated_path}")
        return 0

    stats = export_persona_jsonl(
        repo_root=args.repo,
        output_path=candidates_path,
        max_sessions=args.max_sessions,
        max_pairs=args.max_pairs,
    )
    curation = apply_persona_curation(
        candidates_path=candidates_path,
        curated_path=curated_path,
    )
    print(f"candidates: {candidates_path}")
    print(f"curated:    {curated_path}")
    print(f"sessions:   {stats.sessions_scanned}")
    print(
        f"pairs:      {stats.pairs_written} candidates, "
        f"{stats.pairs_skipped} skipped by filters, "
        f"{curation.curated} curated, "
        f"{curation.rejected} rejected"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
