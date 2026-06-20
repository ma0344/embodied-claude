# Role persistence — SOUL を基底（Deep）に近づける（ma-home）

**目的**: キオスク会話で口調・関係が薄れないよう、`SOUL.md` の核を **プロンプト毎ターン注入** から **推論の安定層** へ移す。

**関連**: [backlog-ma-home.md](./backlog-ma-home.md)（RP / MEM-6）、[backlog-koyori.md](./backlog-koyori.md)、4 層モデルの **Deep** 層。

---

## 二層の脳

| 層 | 置き場 | 更新頻度 |
|----|--------|----------|
| **Deep（基底）** | SOUL.core → stable append / LM Studio system / 将来 LoRA | 低（まー承認） |
| **実行時** | compose / memory / social / STM | 毎ターン |

 episodic な話・今日の出来事は LTM / daybook。**口調と関係のデフォルト** だけ基底へ。

---

## Phase 0 — SOUL.core + stable append（**済**）

| 項目 | 内容 |
|------|------|
| ファイル | `presets/koyori-SOUL.core.md`（コミット可） |
| 注入 | `build_gateway_stable_append()` — KV 安定 `appendSystemPrompt` |
| 上書き | `PRESENCE_SOUL_CORE_PATH` |
| 全文 | `SOUL.md` は `/soul` 明示時のみ `soul_prefetch`（従来どおり） |

**確認**: キオスクで挨拶 → 敬語化・三人称「こより」・assistant 口調が出にくいこと。

---

## Phase 1 — LM Studio 固定 system（**済 — ma-home 2026-06-20**）

1. LM Studio chat モデルの **System Prompt** = `presets/koyori-SOUL.core.md` 全文
2. `.\scripts\enable-rp-phase1-ma-home.ps1` → `PRESENCE_SOUL_CORE_IN_APPEND=0`
3. `.\scripts\restart-presence-ui.ps1`
4. 手順: [lmstudio-model-change.md](./lmstudio-model-change.md) § SOUL.core

**確認**: append に `[SOUL core — mandatory` が**出ない**こと（gateway + voice anchor のみ）。口調は LM Studio system から維持されること。

---

## Phase 2 — Persona LoRA

1. **学習データ**: `{system: SOUL.core, messages: [...]}` — tool call なしの良い会話のみ
2. **export 脚本（RP-2a 済）**:

```powershell
cd C:\Users\ma\src\embodied-claude\presence-ui
uv run python ..\scripts\export-persona-lora-jsonl.py
# 既定出力: %USERPROFILE%\.claude\memories\training\koyori-persona.jsonl
uv run python ..\scripts\export-persona-lora-jsonl.py --dry-run
```

   gateway 注入・敬語・tool 名・挨拶だけのターンは除外。

3. **学習（RP-2b 未）**: bf16 ベースで LoRA → マージ → Q4/QAT GGUF
4. **モデル id**: 例 `google/koyori-gemma-4-12b-qat` を LM Studio 常駐
5. **評価セット**: 敬語率、三人称、assistant 口調、まー呼称

ツール頻度・remember は **gateway 決定論**（LoRA に焼かない）。

---

## Phase 3 — Deep 昇格（MEM-6 接続）

| 準備（Phase 1〜2 と並行） | 内容 |
|---------------------------|------|
| MEM-6 | daybook arc → **SOUL パッチ提案**（人間承認必須） |
| パッチ履歴 | `SOUL.md` diff + 学習 JSONL 追記 |
| LoRA v2 | 承認済みパッチ反映後に再学習 |

自動で重みに書き込まない。提案 → まー OK → SOUL.core / 学習データ更新 → LoRA 差し替え。

---

## 環境変数

| 変数 | 既定 | 意味 |
|------|------|------|
| `PRESENCE_SOUL_CORE_PATH` | `presets/koyori-SOUL.core.md` | stable append 用 core |
| `PRESENCE_SOUL_CORE_IN_APPEND` | `1` | `0` で Phase 1 移行後に append から core を外す |
| `PRESENCE_SOUL_PATH` | プロジェクト `SOUL.md` | 全文 prefetch 用 |
