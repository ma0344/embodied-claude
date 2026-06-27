# WS-5 — 自発 Web 検索

**状態**: 📋 計画済（WS-1〜2c 済の後）  
**親仕様**: [ws-2-conversation-web-search.md](./ws-2-conversation-web-search.md)

---

## 目的

「調べて」等の明示が **なくても**、会話文脈 + plan/initiative で gateway が検索・prefetch。境界・頻度制御付き。

## 現状

`looks_like_web_search_request`（「調べて」等）のみ。自律 tick は `web_search_direct`（別経路）。

## たたき（未実装）

- `compose` / `plan_response` の initiative または専用ヒューリスティクスで「今調べる価値あり」
- 会話 + `open_loops` から query 組み立て（「いい感じ」単体は **検索しない**）
- 既存 `search_prefetch` + `url_prefetch` 再利用
- `evaluate_action` / quiet hours で抑制

## 受け入れ

- サッカー文脈の曖昧発話 → **自発検索しない**
- 具体トピックで事実確認が要るときだけ走る

## 実装順（合意 2026-06-23）

1. WS-1 + WS-3 ✅  
2. WS-2a → 2b → 2c ✅  
3. GAPI  
4. **WS-5**

## 認知層

- **解釈・選択**: 「今調べるか」判定（plan / ルール）
- **感覚・身体**: DDG/Brave + fetch
- **前頭葉（任意）**: query 整形単発 LLM
- **表層**: prefetch 根拠のみ

LW-7（読書 → Web 連鎖）と共通化可 → [alive-lw-read.md](../tracks/alive-lw-read.md)。

全文: [archive § MEM-5j / WS-5](../archive/backlog-ma-home-full-2026-06-26.md#mem-5j--会話中-websearchlm-studio--cc-websearch2026-06-20)
