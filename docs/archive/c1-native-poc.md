# C1 — Native PoC 試験手順

**目的**: `:8090` 上で **8080 プロキシを経由せず** claude-code-server + compose lite が動くか、1 セッションで体感確認する。

本番の部屋（`/`）はそのまま。Native PoC は **並行ルート**（`/poc/native`）。

---

## 前提

- LM Studio 起動済み（`settings.local.json` のモデルと一致）
- `:18900` memory daemon（記憶リスト / compose recall 用）
- **8080 は不要**（Native 経路は Claude CLI を presence-ui 内で直接 spawn）
- `.research/claude-code-server` が clone 済み（`uv sync` は `restart-presence-ui` が実施）

---

## 有効化

```powershell
cd C:\Users\ma\src\embodied-claude
.\scripts\c1-native-poc.ps1 -Enable
```

確認:

```powershell
Invoke-RestMethod http://127.0.0.1:8090/api/v1/health | ConvertTo-Json
# details.native_chat == true
# details.mode == "gateway+native"
```

ブラウザ: **http://localhost:8090/poc/native**  
パスワード: 既定 `koyori-poc`（`PRESENCE_CCS_PASSWORD` で変更可）

---

## 試すこと（15〜20 分）

| # | 入力 | 見るポイント |
|---|------|-------------|
| 1 | `直近10件の記憶リストを出して。` | **Claude 経由せず** direct 返答（8192 ctx 対策）。番号付きリスト |
| 2 | `PR review 明日やるの覚えといて` | 覚えた返答 + `[memory_saved_server]` 相当（PoC log に compose 痕跡） |
| 3 | `続きどうする？` | 直前文脈（PR review）に触れるか。8080 部屋と比較 |
| 4 | `昨日の煎餅の話、覚えてる？` | `[relevant_memories]` / 言い換え想起（Mission A 相当） |

**比較**（任意）: 同じ 2〜4 を本番 `http://localhost:8090/`（8080 プロキシ）でも試し、latency・文脈・口調差をメモ。

---

## 記録テンプレ（まー 2026-06-14 試行）

```
1 記憶リスト direct: OK
2 remember: 1→2連続Sendで session resume エラー → 修正済み（direct は session を mint しない）
   reload 後 remember: OK（input_tokens ~38k — MCP 定義が重い）
3 続きどうする: OK（PR review に触れた）
4 煎餅言い換え: 初回 NG（MCP 演技）→ 修正後 OK（DB「まーは、実は甘いお煎餅が好きだ」一致）
   煎餅 turn: input_tokens ~116k（MCP 定義 ~30k + セッション履歴累積。stdio 再 spawn ではない）
8080 脱却の見立て: 部分採用 — 8080 なしでも会話可。recall は RAG 注入が主、MCP は補助に降格
C2: twicc 見送り — [c2-twicc-decision.md](./c2-twicc-decision.md)
```

---

## 記録テンプレ

```
日付:
モデル:
1 記憶リスト direct: OK / NG —
2 remember 確認: OK / NG —
3 続きどうする: OK / NG —
4 煎餅言い換え: OK / NG —
体感 latency (native vs 8080): 
8080 脱却の見立て: 続行 / 見送り / 部分採用（理由）
```

---

## 無効化（本番に戻す）

```powershell
.\scripts\c1-native-poc.ps1 -Disable
```

`/` 部屋は従来どおり 8080 プロキシ。Native ルートだけ消える。

---

## トラブル

| 症状 | 対処 |
|------|------|
| `/poc/native` 404 | `-Enable` 後に restart 忘れ → `c1-native-poc.ps1 -Enable` 再実行 |
| login 401 | URL `?pw=...` または `PRESENCE_CCS_PASSWORD` |
| Claude spawn 失敗 | `presence-ui.log`、LM Studio / `claude` CLI on PATH |
| compose 古い | `.\scripts\sync-presence-deps.ps1` → restart |
