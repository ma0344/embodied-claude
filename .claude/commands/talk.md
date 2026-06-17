---
description: "まーとの会話ターン — gateway Heartbeat API → 返答 → 記録（MCP sociality 不要）"
allowed-tools:
  - "Bash"
  - "mcp__memory__remember"
  - "mcp__memory__recall"
  - "mcp__memory__list_recent_memories"
  - "mcp__tts__say"
---

# /talk — 1ターンの Heartbeat（v0.3 / BIO-6）

まー（`person_id=ma`）との会話1回分。**compose / plan / record は presence-ui gateway**（`:8090`）。sociality MCP は使わない。

## 手順（順番固定）

1. **compose + plan**（gateway）

```bash
# Bash（Claude Code）— user_text は $ARGUMENTS または会話から
curl -sS -X POST "http://127.0.0.1:8090/api/v1/heartbeat/compose-plan" \
  -H "Content-Type: application/json" \
  -d "{\"person_id\":\"ma\",\"channel\":\"chat\",\"user_text\":\"<まーの発話>\"}"
```

PowerShell の場合:

```powershell
.\scripts\talk-compose.ps1 -UserText "<まーの発話>"
```

レスポンスの `plan` / `ctx` をこのターンの判断として使う。

2. **plan に従って返答**
   - `plan_move` / `plan.primary_move` が `stay_silent` / `defer` → **黙る**
   - `plan.voice.speak=false` → **`say` 禁止**
   - `plan.must_include` / `plan.must_avoid` を守る
   - 口調は **SOUL.md** + compose の `compact_prompt_block`

3. **返答後 — finalize**（experience + pulse + interpretation_shift）

```bash
curl -sS -X POST "http://127.0.0.1:8090/api/v1/heartbeat/finalize-turn" \
  -H "Content-Type: application/json" \
  -d "{\"person_id\":\"ma\",\"user_text\":\"<まーの発話>\",\"reply_text\":\"<こよりの返答>\",\"plan\":<composeのplan>,\"ctx\":<composeのctx>}"
```

PowerShell:

```powershell
.\scripts\talk-finalize.ps1 -UserText "..." -ReplyText "..." -PlanJsonPath plan.json -CtxJsonPath ctx.json
```

4. **記憶** — 残すべき事実があれば `mcp__memory__remember`（HTTP 経由でも可）
5. **音声** — plan が許すなら返答のあと `mcp__tts__say`（`speaker=local`）

## 名前

自分は **こより**。相手は **まー**（`ma`）。

## 禁止

- compose/plan を飛ばして長文だけ返す
- plan が silent なのに喋る
- sociality MCP をこのターンで呼ぶ（gateway と二重になる）

入力: $ARGUMENTS
