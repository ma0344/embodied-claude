"""Merge research outputs into presets/koyori-osaka-grammar.yaml.

Updates:
  - corpus_examples  ← .research/.../out/ksj_examples.json
  - adams_chapters   ← .research/.../out/adams_grammar_index.json

Usage:
  python scripts/sync_osaka_grammar_yaml.py
  python scripts/sync_osaka_grammar_yaml.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
YAML_PATH = ROOT / "presets" / "koyori-osaka-grammar.yaml"
KSJ_JSON = ROOT / ".research" / "osaka-grammar-data" / "out" / "ksj_examples.json"
ADAMS_JSON = ROOT / ".research" / "osaka-grammar-data" / "out" / "adams_grammar_index.json"

ADAMS_MAP = {
    "Negative Verb Conjugation": ["negation"],
    "Plain Copula": ["copula"],
    "To Be, To Exist": ["copula", "existence"],
    "Sentence Final Particle": ["sentence_final"],
    "Expression": ["lexicon"],
    '"Wrong;"': ["judgment"],
    '"Bad;"': ["judgment"],
    '"To Say;"': ["lexicon"],
    '"Good;"': ["adjective"],
    '"Interesting;"': ["adjective"],
    "Genderized Sentence Final": ["sentence_final"],
    "Contracted Adjectives": ["adjective"],
}


def _note_for_text(text: str) -> str:
    if "へん" in text or "ひん" in text:
        return "negation"
    if "ちゃう" in text:
        return "chau"
    if "あかん" in text:
        return "akan"
    if " や " in f" {text} " or text.endswith(" や"):
        return "copula"
    if "ほんま" in text:
        return "emphasis"
    return "dialect"


def _corpus_yaml_block(examples: list[dict[str, str]], *, limit: int = 15) -> str:
    lines = ["corpus_examples:"]
    for item in examples[:limit]:
        speaker = item.get("speaker", "")
        text = item.get("text", "").replace('"', '\\"')
        note = _note_for_text(text)
        lines.append(f"  - speaker: {speaker}")
        lines.append(f'    text: "{text}"')
        lines.append(f"    note: {note}")
    return "\n".join(lines) + "\n"


def _adams_yaml_block(chapters: list[dict[str, object]]) -> str:
    lines = ["adams_chapters:"]
    seen: set[str] = set()
    for ch in chapters:
        title = str(ch.get("title", "")).strip()
        if not title or title in seen:
            continue
        seen.add(title)
        maps = ADAMS_MAP.get(title, ["reference"])
        maps_s = ", ".join(maps)
        lines.append(f"  - title: {title}")
        lines.append(f"    maps_to: [{maps_s}]")
    return "\n".join(lines) + "\n"


def _replace_section(text: str, key: str, new_block: str) -> str:
    pattern = re.compile(rf"^{key}:.*?(?=^[a-z_]+:|\Z)", re.MULTILINE | re.DOTALL)
    if not pattern.search(text):
        return text.rstrip() + "\n\n" + new_block
    return pattern.sub(new_block.rstrip() + "\n", text, count=1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not YAML_PATH.is_file():
        raise SystemExit(f"missing {YAML_PATH}")

    text = YAML_PATH.read_text(encoding="utf-8")

    if KSJ_JSON.is_file():
        ksj = json.loads(KSJ_JSON.read_text(encoding="utf-8"))
        examples = ksj.get("examples", [])
        if isinstance(examples, list):
            text = _replace_section(text, "corpus_examples", _corpus_yaml_block(examples))

    if ADAMS_JSON.is_file():
        adams = json.loads(ADAMS_JSON.read_text(encoding="utf-8"))
        chapters: list[dict[str, object]] = []
        if isinstance(adams, list) and adams:
            first = adams[0]
            if isinstance(first, dict):
                raw = first.get("chapters", [])
                if isinstance(raw, list):
                    chapters = [c for c in raw if isinstance(c, dict)]
        if chapters:
            text = _replace_section(text, "adams_chapters", _adams_yaml_block(chapters))

    if args.dry_run:
        print(text[-2500:])
        return 0

    YAML_PATH.write_text(text, encoding="utf-8")
    print(YAML_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
