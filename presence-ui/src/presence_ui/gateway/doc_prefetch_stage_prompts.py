"""DOC-READ C — e4b confirm for registered-book open candidates."""

from __future__ import annotations


HON_AS_BOOK_SYSTEM = """あなたは日本語の言語解析機です。
与えられたプロンプト中にある「本」という漢字が、文脈の中で、名詞の「本(Book)」という意味で使用されているか否かを答えてください。
「本(Book)」として使われている場合は「本です」、そうでない場合は「本ではありません」の2択で答えてください。"""


def build_doc_intent_system(*, book_title: str, book_aliases: tuple[str, ...]) -> str:
    alias_block = ""
    if book_aliases:
        alias_block = "別名: " + " / ".join(book_aliases) + "\n"
    return f"""あなたは gateway 内部の分類器です。まーの発話が、登録済みの特定の本について議論・深掘り・続きを求めているかだけを判定する。

対象の本:
タイトル: {book_title}
{alias_block}
## 判定基準

open_registered_book=true にするのは、まーが **上記の登録済み本** について話している・読み返したい・続きを求めているときだけ。

false にする例:
- 「本能」「基本」「資本」「山本」など、別語の一部に「本」が含まれるだけ
- 文学・一般論（羅生門、物語、人間の暗さ）で、登録本のタイトル/別名に触れていない
- 天気・雑談・無関係な話題

## 出力

JSON のみ。markdown フェンス禁止。
{{"open_registered_book": true|false, "reason": "短い理由"}}"""


def build_doc_intent_task(*, utterance: str, gate_reason: str) -> str:
    return (
        f"gateway_reason={gate_reason}\n"
        f"utterance={utterance.strip()}\n"
        "open_registered_book を判定して JSON のみ返す。"
    )


def build_hon_as_book_task(*, utterance: str) -> str:
    return utterance.strip()
