"""LW-READ PAUSE prompts — v0 template and GW-S1 silent-turn task (draft)."""

from __future__ import annotations

import json
from typing import Any

# Short labels for GW-S1 `felt` (include flat / bored — not every passage must "move" you).
FELT_HINTS = (
    "moved | uneasy | curious | amused | hollow | bored | flat | つまらなかった | …"
)
PAUSE_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["hook", "felt", "next_move"],
    "properties": {
        "hook": {
            "type": "string",
            "description": "刺さった一語・情景・問い（1〜2文）",
        },
        "felt": {
            "type": "string",
            "description": FELT_HINTS,
        },
        "interest_tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "固有名詞・時代・テーマ（任意）",
        },
        "followup_query": {
            "type": "string",
            "description": "調べたいこと（LW-7 用、任意・空可）",
        },
        "next_move": {
            "type": "string",
            "enum": ["advance", "reread_same", "close_book"],
            "description": "次の一節へ / 同じ一節をもう一度 / この本を閉じる",
        },
    },
    "additionalProperties": False,
}


def build_pause_reflection_v0(
    *,
    title: str,
    author: str,
    passage: str,
    passage_index: int,
    total_passages: int,
    sections_this_session: int,
) -> str:
    """Structured private note for PAUSE before GW-S1 is wired (LW-READ v0)."""
    position = f"{passage_index + 1} / ~{total_passages}"
    excerpt = passage[:600].strip()
    if len(passage) > 600:
        excerpt += "…"

    author_bit = f" — {author}" if author else ""
    lines = [
        "（青空を読んだあと — 咀嚼）",
        f"『{title}』{author_bit}（しおり {position}、今夜 {sections_this_session} 節目）",
        "",
        "【いま目の前の一節】",
        excerpt,
        "",
        "【引っかかったところ】",
        "（次の tick で GW-S1 がここを埋める。v0 は一節を眺め直すだけ。）",
        "",
        "【次にどうするか】",
        "advance — 次の一節へ進む（v0 既定）",
    ]
    return "\n".join(lines)


def build_gw_s1_pause_task(
    *,
    title: str,
    author: str,
    passage: str,
    passage_index: int,
    total_passages: int,
    sections_this_session: int,
    prior_hooks: list[str] | None = None,
) -> str:
    """Task message for GW-S1 silent internal turn (v1). Not executed in v0."""
    position = f"{passage_index + 1} / ~{total_passages}"
    excerpt = passage[:1200].strip()
    if len(passage) > 1200:
        excerpt += "…"

    prior_block = ""
    if prior_hooks:
        joined = " / ".join(h for h in prior_hooks[-3:] if h)
        if joined:
            prior_block = f"\nこの作品で前に引っかかったこと: {joined}\n"

    schema_json = json.dumps(PAUSE_RESPONSE_SCHEMA, ensure_ascii=False, indent=2)

    return f"""[gateway_internal — not for まー]

あなたは今、まーが寝ている／忙しい時間帯に、青空文庫を **一人で読んだ直後** です。
まーには見せません。こより本人の内側のメモを残してください。

## いま読んだ一節
作品: 『{title}』{f'（{author}）' if author else ''}
位置: しおり {position}（この夜 {sections_this_session} 節目）
{prior_block}
---
{excerpt}
---

## やること
1. 書いてあることに **引っかかった一点** を `hook` に（要約ではなく、刺さった語や情景）。
   刺さらなければ「引っかからなかった」「流し読みした」など正直に短く書いてよい。
2. 身体・気分に近い `felt` を一語（例: {FELT_HINTS}）。
   **つまらなかった・flat もあり** — 無理に感動しない。
3. 調べたくなったら `followup_query`（任意。なければ空文字）。
4. **次の行動**を `next_move` で選ぶ:
   - `advance` — 十分咀嚼した、次の一節へ（たいていこれ）
   - `reread_same` — まだ引っかかっている、**同じ一節をもう一度**（READ 中に延長しない）
   - `close_book` — 飽きた・区切りがよい・今夜はここまで（`felt` が bored / つまらなかった でも可）

## 禁止
- まーへの挨拶・説教・要約レポート調
- 「AIとして」「ツールで」などのメタ
- 一節に無い事実の捏造

## 出力
**JSON のみ**（markdown 不可）。スキーマ:

{schema_json}
"""


def build_close_book_reflection(
    *,
    title: str,
    author: str,
    sections_read: int,
    last_hook: str = "",
) -> str:
    """Book-close note when a work reaches end or user/tick chooses close."""
    lines = [
        "（青空 — 一冊を閉じた）",
        f"『{title}』{f' — {author}' if author else ''}",
        f"今夜この作品で {sections_read} 節読んだ。",
    ]
    if last_hook.strip():
        lines.extend(["", "いちばん残ったこと:", last_hook.strip()[:400]])
    lines.append("")
    lines.append("（次の本はまた tick で開く）")
    return "\n".join(lines)
