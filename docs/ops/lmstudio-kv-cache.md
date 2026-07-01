# LM Studio + Claude Code: KV cache と 33k トークン問題

## 結論（先に）

- **Anthropic の `cache_control`（ephemeral）は LM Studio では効かない** — ローカル推論はサーバー側 prompt cache を持たない。
- 再利用できるのは **llama.cpp のセッション内 KV cache** だけ。LM Studio ログの **`f_keep`** を見る（`0.95+` = ヒット、`-1` / `sim=0` = 毎回フル prefill）。
- **~33k トークン**の大半は **MCP ツール定義**（特に `sociality` 30+ 本 + `memory` 20+ 本）。会話文よりデカい。
- **毎ターン変わる hook 注入**（`[associative_recall]` 等）も prefix 安定性を壊す。
- **stdio `memory-mcp` は HTTP daemon と二重起動** → 7h ハングの直接原因になりうる。**日常チャットでは `memory` MCP を外し、hook + `:18900` だけ使う。**

---

## 7 時間「Booping…」が進まない理由

正常フロー（`tool_use` あり）:

1. LM Studio: turn 1 完了 → `Finished streaming Anthropic response`（ここで LM Studio ログは止まって見える）
2. Claude Code: stdio MCP 実行
3. LM Studio: turn 2（tool_result 込み）

ハング時は **2 で止まる**。`memory-mcp`（stdio）が daemon と **同じ `memory.db` / Chroma / E5** を触り、**待ち状態（CPU 0）** になることがある。

確認:

```powershell
Get-Process memory-mcp, claude | Select-Object ProcessName, Id, CPU, StartTime
```

対処:

```powershell
# 詰まった stdio MCP を落とす（daemon は残す）
Stop-Process -Id <memory-mcp-pid> -Force
# Claude Code 側は /clear か Ctrl+C
```

---

## 33k を毎回 prefill する構造

| 塊 | おおよそ | 毎ターン変わる？ |
|----|---------|------------------|
| システム + CLAUDE.md + Skills | 大 | ほぼ固定 |
| **MCP tools JSON** | **最大** | 固定（サーバー構成次第） |
| 会話履歴 | 増える | 末尾だけ増加 → prefix はキャッシュ可 |
| **UserPromptSubmit hook** | 小〜中 | **毎ターン変わる** |
| Gateway `appendSystemPrompt` | 中 | PoC では毎ターン変わる |

112k ctx を確保しても、**毎回 33k prefill** なら GPU は prefill に縛られ、MCP タイムアウトや hook 5s kill も起きやすい。

---

## 対策（優先順）

### 1. 日常チャット用 MCP を絞る（いちばん効く）

**ma-home 適用済み（2026-06-14）**: `.claude/settings.local.json` は daily = `system-temperature` のみ。  
`.mcp.json` は全サーバー定義のまま。切替は `enabledMcpjsonServers` だけ（`_mcp_profile_*` キー参照）。

`settings.local.json`:

```json
"enabledMcpjsonServers": ["system-temperature"]
```

プロファイル例（`_mcp_profile_*` に同内容を記載）:

| 用途 | servers |
|------|---------|
| 日常（8090 / Native） | `system-temperature` |
| 音声 | + `tts` |
| 見る・聞く | + `wifi-cam` |
| `/talk` Heartbeat | `system-temperature`, `memory`, `sociality` |
| 全部（旧 default） | 上記 + `tts`, `wifi-cam` |

- **`memory` を外す** — 保存・想起は hook（`:18900`）が担当。Gemma に `recall` させない。
- **`sociality` を外す** — ツール定義が最大。`/talk` や `:8090` compose が要るときだけ戻す。
- **`wifi-cam` を外す** — 見る・聞くターンだけ有効化。

目安: MCP 5 本 → 1〜2 本で **入力 15k〜20k 減** もありうる。

**本線（2026-06-14）**: 手動プロファイルは移行期。desire / see / say は [gateway-direct-actions.md](./gateway-direct-actions.md) の gateway 直実行へ。daily MCP slim はそのまま維持。

### 2. LM Studio 側

| 設定 | 推奨 |
|------|------|
| Max Concurrent Predictions | **1**（KV スロット eviction 防止） |
| Unified KV Cache (Experimental) | **ON**（安定なら） |
| モデルをメモリに保持 | ON |
| Context 112k | OK — ただし KV は長いほど VRAM 食う。prefill 自体は短くした方が速い |

ログで確認:

```
f_keep = 0.99   # 99% prefix 再利用
f_keep = -1.000 # フル prefill（キャッシュミス）
```

2 ターン目以降も `f_keep=-1` 続き → MCP 削減 + hook 安定化 + 並列 1 を疑う。

### 3. hook タイムアウト

`settings.json` の UserPromptSubmit は **30 秒**（E5 warm ~9s + remember を考慮）。  
5 秒だと `[memory_saved_server]` が JSONL に載らず db だけ更新される。

**koyori-surface**（Native chat cwd）では hook を切る。compose / plan は gateway が `[gateway_turn_context]` で注入。

### 3b. 表層会話 cwd（koyori-surface）

Native chat の `claude` 子プロセスは **`presence-ui/koyori-surface/`** を cwd（`PRESENCE_CHAT_WORKING_DIR`）。
薄い `CLAUDE.md` のみ — 開発用の厚い `CLAUDE.md` はリポジトリルート（Cursor）。

**注意**: Claude Code は cwd から親へ遡って `CLAUDE.md` を全部読む。surface がリポ内にあるとルートの設備マニュアルも載る。
→ `.claude/settings.local.json` の **`claudeMdExcludes`** で除外（起動時に `ensure_chat_surface_settings()` が同期）。

| 経路 | cwd |
|------|-----|
| Cursor / 開発 | `embodied-claude/` |
| Native chat / キオスク | `presence-ui/koyori-surface/` |

戻す: `PRESENCE_CHAT_USE_REPO_ROOT=1`

### 4. PoC / 8090（実装済み 2026-06）

既定 `PRESENCE_KV_STABLE_APPEND=1`:

- **`appendSystemPrompt`** … 毎ターン同一の `[Gateway — stable]`（compose/plan の説明のみ）
- **`message`** … `[gateway_turn_context]` + compose/plan 全文 + まーの発話（hook と同思想）

compose / plan は **毎ターン Gateway で実行** — 判断機構は変わらない。載せ方だけ変更。

レガシー（毎ターン append 差し替え）: `PRESENCE_KV_STABLE_APPEND=0`

### 5. やらない方がいい期待

- Claude API の `cache_read_input_tokens` が LM Studio で増える — **期待しない**
- ctx 112k にしたから prefill が速くなる — **長いほど初回 prefill は重い**

---

## 確認手順（2 ターン test）

1. `enabledMcpjsonServers` を 1 本に絞る
2. LM Studio Concurrent = 1
3. 同セッションで「こんばんは」→「元気？」
4. 2 ターン目のログで `f_keep` と prompt eval 時間を比較

1 ターン目: 20s prefill でも許容。2 ターン目: **1〜3s** なら KV 再利用成功。

---

## 関連

- [mission-A_Investigation-Report.md](./mission-A_Investigation-Report.md) — compose / hook / MCP 二重経路
- [backlog-ma-home.md](./backlog-ma-home.md) — Gemma remember 信頼性、hook UX
