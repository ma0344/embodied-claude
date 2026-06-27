# GAPI — Google Calendar / Drive

**状態**: 📋 WS 完了後着手  
**関連**: [ws-2-conversation-web-search.md](../ops/ws-2-conversation-web-search.md)、[open-loops-reminders.md](../architecture/open-loops-reminders.md)

---

## きっかけ（2026-06-23）

こよりに **Google カレンダー**（予定）と **Google ドライブ**（共有ドキュメント）へアクセス。会話・自律・OL と接続。

## 原則

| 原則 | 内容 |
|------|------|
| 読み取り優先 | v0 は Calendar + Drive 読取。書き込みは後追い |
| gateway 直実行 | WS-2 / see_prefetch と同型 — LLM にツール名を選ばせない |
| 境界 | 全 Drive ではなく **共有フォルダ** — `socialPolicy` + boundary |
| 認証 | OAuth または SA。トークンは git 外 |
| 記憶 | 全文 LTM 化しない。salient + open loop / commitment |

## ユースケース

- 「今日の予定は？」→ Calendar prefetch、**捏造しない**
- 「ドライブの〇〇」→ `[drive_prefetch]` 注入
- OL2 と Calendar **due 整合**（GAPI-3）

## アーキテクチャ

```
まー発話 / tick
  → intent（calendar_query / drive_search）
  → gateway prefetch（Google API）
  → [calendar_prefetch] / [drive_prefetch]
  → compose / plan → 応答
```

**WS との関係**: 公開 URL は WS-2b/c。Drive 内社内様式は GAPI-4。

---

## 実装 ID

| ID | 内容 | 状態 |
|----|------|------|
| GAPI-0 | ポリシー・スコープ | 未 |
| GAPI-1 | OAuth / `GOOGLE_*` env | 未 |
| GAPI-2 | Calendar 読取 prefetch | 未 |
| GAPI-3 | OL / Calendar 突合 | 未 |
| GAPI-4 | Drive 読取・要約（bounded） | 未 |
| GAPI-5 | `koyori/status` 接続状態 | 未 |

**実装順（合意）**: WS-1〜2c 完了後。GAPI-0 から。

---

## 認知層

- **感覚・身体**: Google API HTTP
- **前頭葉**: 要約 LLM（単発）、スコープチェック
- **表層**: prefetch 根拠のみ述べる

全文: [archive § GAPI](../archive/backlog-ma-home-full-2026-06-26.md#gapi--google-calendar--drive合意-2026-06-23)
