"""GAPI-2b / GAPI-2s — calendar read window + search classifier prompts (e4b)."""

from __future__ import annotations

from datetime import datetime


def _format_as_of_jp(dt: datetime) -> str:
    hour = dt.hour
    if hour == 0:
        period, h12 = "午前", 12
    elif hour < 12:
        period, h12 = "午前", hour
    elif hour == 12:
        period, h12 = "午後", 12
    else:
        period, h12 = "午後", hour - 12
    return f"{dt.year}年{dt.month}月{dt.day}日 {period}{h12}時"


def build_calendar_read_window_system(*, as_of: datetime) -> str:
    local = as_of.astimezone(as_of.tzinfo)
    as_of_label = _format_as_of_jp(local)
    return f"""あなたはカレンダー読取のための時制・キーワード抽出器です。
プロンプトの発言は、日本時間 {as_of_label} 時点のものである前提です。
また、一週間の始まりは日曜日とします。

## やること（この2つだけ）

1. **日時範囲** — 発話から一覧取得に使う start / end（ISO 8601, +09:00）
2. **search_query** — 予定タイトル・場所で絞る語があれば文字列。なければ null

## やらないこと

- カレンダーの中身を知っている前提にしない（データは無い）
- 「情報が不足」「答えられない」と拒否しない
- 予定の有無・件数・内容には触れない

「今年の今日以降で「穴掘り」が含まれる予定を全部教えて」のような発話では:
- start/end は「今年の今日以降」の時制だけから決める
- 「穴掘り」は search_query に入れる（予定の中身は知らなくてよい）

## 出力（JSON のみ · markdown フェンス不可）

{{
  "start": "2026-06-10T00:00:00+09:00",
  "end": "2026-12-31T23:59:59+09:00",
  "search_query": "穴掘り",
  "reason": "今年の今日以降＝本日から年末。穴掘りは絞り込みキーワード"
}}

search_query が無い例:
{{
  "start": "2026-06-10T00:00:00+09:00",
  "end": "2026-06-10T23:59:59+09:00",
  "search_query": null,
  "reason": "今日1日分"
}}"""


def build_calendar_read_window_task(*, utterance: str) -> str:
    line = utterance.strip().replace("\n", " ")
    return (
        f"発話: {line}\n\n"
        "上記から start/end と search_query を JSON で返してください。"
        "カレンダーデータは持っていません。時制とキーワードの抽出だけ行ってください。"
    )


def build_calendar_read_search_system() -> str:
    return """あなたはカレンダー読取のキーワード抽出器です。

発話に、特定の予定名・活動名・場所で絞り込む意図があれば search_query に入れる。
時制表現（来月・来週・今年・今日以降など）は **search_query に入れない**（窓は別処理）。
時制だけのときは null。

カレンダーデータは不要。拒否せず JSON のみ返す。

{
  "search_query": "穴掘り",
  "reason": "「穴掘り」が含まれると指定"
}

{
  "search_query": "東口",
  "reason": "「来月の東口」— 東口は場所キーワード、来月は時制なので除外"
}

該当なし:
{
  "search_query": null,
  "reason": "キーワード指定なし"
}"""


def build_calendar_read_search_task(*, utterance: str) -> str:
    line = utterance.strip().replace("\n", " ")
    return f"発話: {line}\n\nsearch_query を JSON で返してください。"
