"""Extract Osaka-flavoured subject (*s:) lines from KVJ KSJ_noPOS interviews.

Reads speaker metadata + noPOS text files (default: user Downloads folder).
Writes UTF-8 JSON for curating presets/koyori-osaka-grammar.yaml examples_good.

Usage:
  python scripts/extract_ksj_examples.py
  python scripts/extract_ksj_examples.py --ksj-dir "C:/Users/ma/Downloads/KSJ_noPOS" --out .research/osaka-grammar-data/out/ksj_examples.json
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KSJ_DIR = Path.home() / "Downloads" / "KSJ_noPOS"
DEFAULT_OUT = ROOT / ".research" / "osaka-grammar-data" / "out" / "ksj_examples.json"

# Osaka-prefecture-strong young female speakers (codes from KVJ metadata).
# Birth or upbringing in 大阪府 with native index 2 on that field.
DEFAULT_SPEAKER_SUFFIXES = (
    "002F3",
    "005F3",
    "010F3",
    "051F4",
    "055F4",
    "079F4",
    "085F4",
    "111F4",
    "154F3",
)

SKIP_LINE = re.compile(
    r"おねしゃーす|出身|どこ|幼稚園|学歴|職業|バイト|スタート|現住所|"
    r"大学\s*なう|叙々苑|焼肉|受かっ|インタビュー",
)
DIALECT_HINT = re.compile(
    r"へん|ひん|やな|やで|やねん|やろ|あかん|ちゃう|おもんない|おもろ|"
    r"どない|せえ|せん|知らへん|できへん|ほんま|やば|〜",
)
STANDARD_LEAK = re.compile(r"です|ます|でしょう|ません")


@dataclass(frozen=True)
class Example:
    speaker: str
    text: str
    source_file: str


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Extract KSJ_noPOS subject-line examples")
    p.add_argument("--ksj-dir", type=Path, default=DEFAULT_KSJ_DIR)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--min-len", type=int, default=10)
    p.add_argument("--max-len", type=int, default=72)
    p.add_argument(
        "--speakers",
        nargs="*",
        default=list(DEFAULT_SPEAKER_SUFFIXES),
        help="File suffixes like 002F3 (maps to KSJ002F3_noPOS.txt)",
    )
    return p.parse_args()


def extract_examples(
    *,
    ksj_dir: Path,
    speakers: tuple[str, ...],
    limit: int,
    min_len: int,
    max_len: int,
) -> list[Example]:
    if not ksj_dir.is_dir():
        raise FileNotFoundError(f"KSJ_noPOS directory not found: {ksj_dir}")

    per_speaker: dict[str, list[Example]] = {s: [] for s in speakers}
    seen: set[str] = set()

    def consider(suffix: str, text: str, source_file: str) -> None:
        if text in seen:
            return
        seen.add(text)
        per_speaker[suffix].append(Example(speaker=suffix, text=text, source_file=source_file))

    for suffix in speakers:
        path = ksj_dir / f"KSJ{suffix}_noPOS.txt"
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not raw.startswith("*s:"):
                continue
            text = raw[3:].strip()
            if not (min_len <= len(text) <= max_len):
                continue
            if SKIP_LINE.search(text):
                continue
            if STANDARD_LEAK.search(text):
                continue
            if not DIALECT_HINT.search(text):
                continue
            consider(suffix, text, path.name)

    # Round-robin across speakers so one interview does not dominate.
    picked: list[Example] = []
    queues = [per_speaker[s] for s in speakers if per_speaker[s]]
    while queues and len(picked) < limit:
        next_queues: list[list[Example]] = []
        for q in queues:
            picked.append(q.pop(0))
            if len(picked) >= limit:
                return picked
            if q:
                next_queues.append(q)
        queues = next_queues
    return picked


def main() -> int:
    args = _parse_args()
    examples = extract_examples(
        ksj_dir=args.ksj_dir,
        speakers=tuple(args.speakers),
        limit=args.limit,
        min_len=args.min_len,
        max_len=args.max_len,
    )
    payload = {
        "ksj_dir": str(args.ksj_dir),
        "speaker_filter": list(args.speakers),
        "count": len(examples),
        "examples": [
            {"speaker": e.speaker, "text": e.text, "source": e.source_file} for e in examples
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
