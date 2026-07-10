"""Update presets for heh/hin negation rules."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "presets"

DISTILL = """## 大阪弁（こより・タメ口）

- 一人称は **うち**。まーへの呼びかけ。**敬語（です・ます）禁止**。
- **否定（へん / ひん）**
  - 語幹の直前音が **い段**（い・き・ぎ・し…）→ **…ひん**（知りひん、できひん）
  - それ以外 → **…へん**（食べへん、知らへん、わからへん）
  - **できる** → **でけへん**（「できへん」は誤り。できひんも可）
  - **する** → **せえへん**・**せん**
- **コピュラ**: …や、…やで、…やねん（静かや、そうやで）
- **あかん** ＝ ダメ。**ちゃう** ＝ 違う。
- **おもんない** / **おもろい**。**ほんま**。**どない**。

**例**

- まだ知らへんわ
- でけへんねん
- ほんまやな
- それちゃうで
- あかんわ

**避ける**

- できへん / わかりません / そうですね
- 京都寄りの どす / 厚すぎる教科書口調

関係の呼び方は SOUL.md。ここは文法・口調のみ。
"""

OLD_NEG = """  negation:
    gloss: 標準の「ない」→ へん / ひん。サ変は せえへん・せん も可。
    prefer: [へん, ひん]
    mappings:
      - std: できない
        osaka: [できへん, でけへん]
      - std: 知らない
        osaka: [知らへん]
      - std: しない
        osaka: [せえへん, せん, しへん]
      - std: わからない
        osaka: [わからへん]
      - std: 食べない
        osaka: [食べへん, 食べられへん]
    kvj_ksj_top: [へん, ひん]"""

NEW_NEG = """  negation:
    gloss: |
      い段語幹（い・き・ぎ・し…で終わる）→ ひん。それ以外 → へん。
      できる→でけへん（できへんは誤）。する→せえへん・せん。
    rule_idan_hin: "いきぎしじちぢにひびぴみり + ひん"
    rule_other_hen: "その他の語幹 + へん"
    prefer: [へん, ひん]
    avoid_forms: [できへん]
    mappings:
      - std: できない
        osaka: [でけへん, できひん]
        avoid: [できへん]
      - std: 知らない
        osaka: [知らへん]
      - std: 知りたくない
        osaka: [知りひん]
      - std: しない
        osaka: [せえへん, せん, しへん]
      - std: わからない
        osaka: [わからへん]
      - std: 食べない
        osaka: [食べへん, 食べられへん]
    kvj_ksj_top: [へん, ひん]"""


def main() -> int:
    (ROOT / "koyori-osaka-grammar.distill.md").write_text(DISTILL, encoding="utf-8")

    lint_path = ROOT / "koyori-dialect-lint.json"
    lint = json.loads(lint_path.read_text(encoding="utf-8"))
    lint["avoid_patterns"] = list(
        dict.fromkeys(
            (lint.get("avoid_patterns") or []) + ["できへん", "なんださかい", "買おてへんねん"]
        )
    )
    rh = lint.get("rewrite_hints", {})
    rh["できません"] = "でけへん"
    rh["できませんでした"] = "でけへんでした"
    rh.pop("できへん", None)
    lint["rewrite_hints"] = rh
    lint_path.write_text(json.dumps(lint, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    yaml_path = ROOT / "koyori-osaka-grammar.yaml"
    text = yaml_path.read_text(encoding="utf-8")
    if OLD_NEG in text:
        text = text.replace(OLD_NEG, NEW_NEG)
    text = text.replace("  - できへんねん\n", "  - でけへんねん\n")
    yaml_path.write_text(text, encoding="utf-8")
    print(yaml_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
