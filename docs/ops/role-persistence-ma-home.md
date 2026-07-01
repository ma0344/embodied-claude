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
# 既定出力: candidates → curated（%USERPROFILE%\.claude\memories\training\）
uv run python ..\scripts\export-persona-lora-jsonl.py --dry-run
```

   gateway 注入・敬語・tool 名・挨拶だけのターンは除外。**Claude CLI の `No response requested.` も除外**。**メタ報告**（括弧だけの「（今、もう一回言ったで！）」等）・**声/TTS テスト依頼**（「言ってみて」「もう一回」等）・**手続き報告**（短い「言った/試した/聞こえた」系）も除外。**近い assistant 重複**はクラスタごと全部落とす（1 件だけ残さない）。カレンダー読取が増えると「来月の〇〇の予定やね。カレンダー見たら…」のような**テンプレ返答がクラスタ化して候補が減る**のは意図どおり（LoRA に定型応答を焼かない）。

   **export 窓**: 直近 **40 セッション**（`--max-sessions` で拡張可）。再 export は candidates を上書き；`koyori-persona-rejected.json` の人手除外は維持。

   **JSONL の system 行**: 1 ペアごとに SOUL.core が載るのは SFT データセットの一般的な形（学習ツールが行単位で読むため）。推論時は LM Studio の固定 system + LoRA なので**二重にはならない**。ファイルサイズを減らしたい場合は学習設定側で `system` テンプレを1回だけ指定し、export を `--messages-only` 化する拡張は RP-2b で検討可。

   **export 出力（2 ファイル + manifest）**:
   - `koyori-persona-candidates.jsonl` — フィルタ済み候補（再 export で上書き）
   - `koyori-persona.jsonl` — **LoRA 学習用**（候補 − 人手除外）
   - `koyori-persona-rejected.json` — 除外 fingerprint（再 export 後も維持）

   **Phase 2c — Persona Inner（内省）** ✅ export / review

   表層会話に加え、**非公開の一人称散文**（private_reflection · overnight inner voice）を別 JSONL で LoRA 素材にする。

   | ファイル | 内容 |
   |---------|------|
   | `koyori-persona-inner-candidates.jsonl` | 内省候補 |
   | `koyori-persona-inner.jsonl` | 内省 LoRA 学習用 |
   | `koyori-persona-inner-rejected.json` | 内省除外 manifest |
   | `inner-voice-archive.jsonl` | dreaming 時の overnight inner voice 履歴（追記のみ） |

   ```powershell
   cd C:\Users\ma\src\embodied-claude\presence-ui
   uv run python ..\scripts\export-persona-inner-jsonl.py
   ```

   - **素材**: `private_reflections`（social.db）· `inner-voice-archive.jsonl`
   - **user cue**: `（内省・非公開）{title}` 等（まーの実発話ではない）
   - **入れない**: compose / plan / dream_digest 箇条書き / GW JSON
   - **学習 mix 目安**: surface : inner = **4:1 〜 3:1**（RP-2b）
   - **review**: `http://localhost:8090/training/persona` → **内省** タブ

   **ブラウザで確認（ma-home）**:

   `http://localhost:8090/training/persona` — **会話** / **内省** タブ。内省は `POST /api/v1/training/persona-inner/export` 等。

   **プレビュー（Markdown）**:

```powershell
cd C:\Users\ma\src\embodied-claude\presence-ui
uv run python ..\scripts\preview-persona-lora-jsonl.py
# 既定: 同じ JSONL 隣の koyori-persona.md に出力
uv run python ..\scripts\preview-persona-lora-jsonl.py -o preview.md --limit 20
```

3. **学習（RP-2b 未）**: bf16 ベースで LoRA → マージ → Q4/QAT GGUF

   **更新 cadence（合意）**: 日次 LoRA 再学習はしない。週次 or 節目で export → ブラウザ/`preview` で目視 → **良いペア +30〜50** または月1で再学習。SOUL パッチ承認後は LoRA v2（Phase 3）。

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
| `PERSONA_TRAINING_JSONL` | `~/.claude/memories/training/koyori-persona.jsonl` | LoRA 学習 JSONL（候補 − 人手除外） |
| `PERSONA_TRAINING_CANDIDATES_JSONL` | `~/.claude/memories/training/koyori-persona-candidates.jsonl` | export 候補（review 対象） |
| `PERSONA_TRAINING_REJECTED_JSON` | `~/.claude/memories/training/koyori-persona-rejected.json` | 人手除外 manifest |
| `PERSONA_INNER_TRAINING_JSONL` | `~/.claude/memories/training/koyori-persona-inner.jsonl` | 内省 LoRA 学習 JSONL |
| `PERSONA_INNER_TRAINING_CANDIDATES_JSONL` | `~/.claude/memories/training/koyori-persona-inner-candidates.jsonl` | 内省 export 候補 |
| `PERSONA_INNER_TRAINING_REJECTED_JSON` | `~/.claude/memories/training/koyori-persona-inner-rejected.json` | 内省人手除外 |
| `PERSONA_INNER_VOICE_ARCHIVE_JSONL` | `~/.claude/memories/training/inner-voice-archive.jsonl` | overnight inner voice 履歴 |
