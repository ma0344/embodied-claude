# C2 — twicc 評価 / 見送り判断

**日付**: 2026-06-14  
**前提**: C1 Native PoC を 1 セッション試行済み（部分採用の見立て）

---

## 比較対象

| | **8090 本番（8080 プロキシ）** | **C1 Native PoC** (`claude-code-server`) | **twicc** (`.research/twicc`) |
|---|------------------------------|------------------------------------------|-------------------------------|
| 役割 | こよりの部屋 + gateway compose / ingest | 8080 バイパス試作 | Claude Code + Codex 汎用 Web UI |
| スタック | FastAPI gateway + sugyan webui | FastAPI + CCS embed | Django 6 + Vue 3 + SQLite JSONL index |
| compose 注入 | gateway `intercept_chat_request` | 同左（`config_factory`） | **なし**（素の Agent SDK セッション） |
| 8080 依存 | **あり** | **なし** | **なし**（自前 UI） |
| セッション管理 | presence registry + social.db | CCS セッション + direct 経路 | `~/.claude/projects/` JSONL 同期・検索・コスト |
| ma-home 適合 | 本番 | PoC 合格（部分） | 要大幅カスタム |

---

## twicc が足すもの（C1 / 8090 に無い）

- プロジェクト横断の **セッション一覧・検索・コスト集計**
- **Codex** 併用 UI（ma-home では未使用）
- モバイル向け UI、組込ターミナル、ツール承認 UX
- JSONL → SQLite の **履歴インデックス**（Tantivy 検索含む）
- クラウド API 向け quota / pricing モニタ

## twicc が解決しないもの（C1 で判明した痛点）

- **MCP ツール定義のトークン膨張** — twicc も Claude Agent SDK 経由で同じ CLI/MCP スタック
- **compose / memory HTTP 注入** — 標準機能ではない。gateway 相当を自前で差し込む必要あり
- **LM Studio + ローカル Gemma** — twicc は Anthropic/OpenAI 本番 API 想定が強い

---

## C1 結果との関係

C1 で確認できたこと:

| 要件 | Native PoC |
|------|------------|
| 8080 なしで会話 | OK |
| compose lite（remember / 文脈 / RAG recall） | OK（direct 経路 + `GATEWAY_STABLE_APPEND`） |
| セッション継続 | OK（修正後） |
| トークンコスト | **重い**（~38k〜116k input；MCP 定義 + 履歴） |
| 本番部屋の完全置換 | **まだ不可** — 116k は Gemma 112k ctx と相性悪い |

→ **8080 脱却の「チャット経路」は PoC で賄える**。  
→ **twicc を入れてもトークン問題は残る**し、compose 注入は PoC 以上の改造が要る。

---

## 判断: **見送り**（アイデア借用のみ）

**採用しない理由**

1. **アーキテクチャ不一致** — Django + Vue フルスタックを presence-ui に統合するコストが、得られる機能（セッション browser / mobile）に対して大きすぎる。
2. **本体優先方針** — backlog 方針どおり「こより本体（記憶・MCP・compose）を先に固める」。UI 探索は C1 で十分な結論が出た。
3. **C1 が役割を被る** — 8080 バイパス + compose 注入は `claude-code-server` embed で既に実証。twicc はこの経路を置き換えない。
4. **ローカル LLM 向けでない** — ma-home の主戦場（LM Studio / Gemma / MCP 削減）は twicc の強みとずれる。

**将来 borrowed 候補（今はやらない）**

- JSONL セッションの **一覧・検索 UI** パターン（8090 サイドバー強化時）
- モバイル向け **タッチ UX**（外出 Tailscale 時）
- セッション **コスト表示**（クラウド API に戻す場合のみ）

---

## 次アクション（C 系）

| 項目 | 内容 |
|------|------|
| C1 | `[x]` 部分採用 — `/poc/native` 維持、本番 `/` は 8080 のまま |
| C2 | `[x]` twicc **見送り**（本 doc） |
| 任意 | Native 経路の MCP 絞り（`docs/lmstudio-kv-cache.md` 参照）で 116k → ~40k 狙い |
| 任意 | `c1-native-poc.ps1 -Disable` — 試験終了なら本番のみに戻す |

---

## 116k input_tokens について（C1 補足）

**「MCP 群を再度読み込んだ」= 毎ターン stdio でサーバー再起動** という意味では **No**。

**Yes に近い部分**:

- Claude CLI セッションの **各 LLM リクエスト** には、設定済み MCP の **ツール定義 JSON** が載る（~30k 級、`docs/lmstudio-kv-cache.md`）
- 同一セッション内の **過去ターン**（ユーザー発話・assistant・tool_result）も累積
- 煎餅試行で `num_turns: 2` なら、1 回 tool 往復 + その結果も含む

remember ~38k → 煎餅 ~116k の差は、**セッション履歴の積み上げ** が主因と見るのが自然。MCP 定義自体は毎ターン載るが、116k の大半は「再 spawn」ではなく **コンテキストウィンドウの中身**。
