"""Extract koyori-relevant accent lines from docs/GL_22_16.pdf (福盛 GL notation).

Writes presets/koyori-osaka-accent-phrases.yaml

Usage:
  python scripts/extract_osaka_accent_phrases.py
  python scripts/extract_osaka_accent_phrases.py --pdf docs/GL_22_16.pdf
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

try:
    import pypdf
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pip install pypdf") from exc

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF = ROOT / "docs" / "GL_22_16.pdf"
DEFAULT_OUT = ROOT / "presets" / "koyori-osaka-accent-phrases.yaml"

# Fukumori H/L tail (allows L0(～H0), H0+H1→H4, L2+↑, H3+F, etc.)
_ACCENT_TAIL = re.compile(
    r"((?:H|L)\d(?:\([^)]*\))?(?:\+(?:H|L)\d+(?:→(?:H|L)\d+)?)?(?:\+↑)?(?:\+F(?:→H\d+)?)?)\s*$"
)
_LINE = re.compile(r"^[\s\u3000]*(.+?)[\s\u3000]+" + _ACCENT_TAIL.pattern)

# Inferred when exact phrase missing (base accent from PDF + memo).
INFERRED: dict[str, tuple[str, str]] = {
    "でけへんねん": ("H1", "inferred: でけへん H1 + ねん"),
    "わからへんねん": ("H2", "inferred: わからへん H2 + ねん"),
    "せえへんけど": ("H1", "inferred: せえへん H1 + けど"),
    "知らへんわ": ("H2", "inferred: proxy わからへん H2"),
    "ほんまやな": ("L3", "inferred: ほんまや L3 + な"),
    "おもろいわ": ("H2", "inferred: おもろい H2 + わ"),
    "やろ": ("L2", "inferred: proxy なんやろ L2"),
}

# Koyori staples — order preserved; accent filled from PDF when exact match exists.
SEED_PHRASES: list[tuple[str, str]] = [
    # 否定
    ("でけへん", "negation"),
    ("でけへんねん", "negation"),
    ("わからへん", "negation"),
    ("わからへんねん", "negation"),
    ("せえへん", "negation"),
    ("せえへんけど", "negation"),
    ("知らへんわ", "negation"),
    # あかん
    ("あかん", "akan"),
    ("あかんわ", "akan"),
    ("あかんねん", "akan"),
    # ちゃう
    ("ちゃうで", "chau"),
    ("それちゃうで", "chau"),
    # コピュラ・断定
    ("ほんまや", "copula"),
    ("ほんまやな", "copula"),
    ("ほんまやねん", "copula"),
    ("そうや", "copula"),
    ("ええんやで", "copula"),
    # あるもん・説明
    ("あるもんや", "affirm"),
    # 疑問
    ("どないしたん", "question"),
    ("どないしたんや", "question"),
    ("なんやねん", "question"),
    ("どうやねん", "question"),
    # お願い・リアクション
    ("いうてくれへんか", "request"),
    ("おもろい", "reaction"),
    ("おもろいわ", "reaction"),
    # よく使う終助
    ("ちゃうわ", "particle"),
    ("やろ", "particle"),
]


def _extract_pdf_text(pdf_path: Path) -> str:
    reader = pypdf.PdfReader(str(pdf_path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _parse_pdf_lines(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("--"):
            continue
        m = _LINE.match(line)
        if not m:
            continue
        phrase = m.group(1).strip()
        accent = m.group(2).strip()
        # Skip kanji lemma headers like あかん(いけない) when bare form also exists
        bare = phrase.split("(")[0].strip()
        found[phrase] = accent
        if bare and bare != phrase:
            found.setdefault(bare, accent)
    return found


def _yaml_quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_yaml(rows: list[dict[str, str]]) -> str:
    lines = [
        "# Osaka accent phrases — Tier 2 (福盛 GL_22_16.pdf)",
        "# TTS POC / reference only. Not injected into 12b prompt.",
        "#",
        "# accent: 京阪式 H/L + 下降位置 (see docs/tracks/osaka-accent-intonation.md)",
        "# TBD = PDF に同一表記なし。近い句のアクセントを目視で補う。",
        "",
        "meta:",
        "  source: docs/GL_22_16.pdf",
        "  notation: fukumori_hl",
        "  status: seed",
        f"  count: {len(rows)}",
        "",
        "phrases:",
    ]
    for row in rows:
        lines.append(f"  - text: {_yaml_quote(row['text'])}")
        lines.append(f"    accent: {_yaml_quote(row['accent'])}")
        lines.append(f"    tag: {_yaml_quote(row['tag'])}")
        if row.get("note"):
            lines.append(f"    note: {_yaml_quote(row['note'])}")
    lines.append("")
    return "\n".join(lines)


def _lookup(pdf_map: dict[str, str], phrase: str) -> tuple[str, str]:
    if phrase in pdf_map:
        return pdf_map[phrase], ""
    if phrase in INFERRED:
        return INFERRED[phrase]
    # Prefix match for compound (e.g. それちゃうで → ちゃうで)
    for key, accent in pdf_map.items():
        if phrase.endswith(key) and len(key) >= 3:
            return accent, f"suffix match: {key}"
    return "TBD", "manual lookup in GL_22_16.pdf"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if not args.pdf.is_file():
        raise SystemExit(f"missing PDF: {args.pdf}")

    pdf_map = _parse_pdf_lines(_extract_pdf_text(args.pdf))
    rows: list[dict[str, str]] = []
    for text, tag in SEED_PHRASES:
        accent, note = _lookup(pdf_map, text)
        rows.append({"text": text, "accent": accent, "tag": tag, "note": note})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(build_yaml(rows), encoding="utf-8")
    matched = sum(1 for r in rows if r["accent"] != "TBD")
    print(f"{args.out} ({len(rows)} phrases, {matched} with accent from PDF)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
