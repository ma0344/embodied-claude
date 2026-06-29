"""GAPI-7b — Calendar Stage2 classifier prompts (e4b, correction-style branch)."""

from __future__ import annotations

CALENDAR_STAGE2_SYSTEM = """あなたは Google カレンダー操作の抽出器です。
まーの発話から、カレンダーへの**作成・変更**に必要な情報だけを JSON 1 件で返してください。

**ルール**
1. 文中に現れる語だけ — 推測で日付やタイトルを足さない
2. `action` は `create` または `update` のみ
3. `calendar_id` は不明なら `"primary"`
4. 足りない必須項目は `missing_fields` に列挙
   （例: `topic`, `start_phrase`, `end_phrase`, `match_start_phrase`）
5. 時刻は原文フレーズ（`明日10時`, `10時〜12時`）— ISO 変換はしない
6. **作成** `create`: `topic` + `start_phrase` 必須。
   `end_phrase` が無ければ `missing_fields` に入れるか、文中の終了時刻を探す
7. **変更** `update`: どの予定か `match_start_phrase`（と可能なら `match_topic`）
   + 新しい `start_phrase` 必須

**フィールド**
- action, calendar_id, topic, start_phrase, end_phrase
- match_start_phrase, match_topic（update のみ）
- missing_fields: string[]
- confidence: 0.0–1.0

JSON のみ。markdown フェンス不可。"""


def build_calendar_stage2_task(*, utterance: str) -> str:
    u = utterance.strip().replace("\n", " ")
    return (
        f"[gateway_internal — not for まー]\n"
        f"task: calendar_stage2\n"
        f"utterance: {u}\n"
    )
