# koyori バックログ — トピック索引

**ダッシュボード**: [backlog-ma-home.md](./backlog-ma-home.md)  
**読み方**: [README.md](./README.md) · [archive-index.md](./archive/archive-index.md)

---

## ma-home トラック

| トピック | 状態 | 読む場所 |
|---------|------|----------|
| **設計方針** | ✅ | [architecture/cognitive-layers.md](./architecture/cognitive-layers.md) |
| **ALIVE / LW** | 🔥 | [tracks/alive-lw-read.md](./tracks/alive-lw-read.md) |
| **GW-SILENT** | ✅ S1 · ✅ S2（opt-in） | [tracks/gw-silent.md](./tracks/gw-silent.md) |
| **OL5** | ✅ 運用確認済 | [tracks/ol5.md](./tracks/ol5.md) |
| **MEM-8** | 概念済 · **8g** 💤 · **8h** 📋 | [architecture/mem-8-encode-retrieve.md](./architecture/mem-8-encode-retrieve.md) · [tracks/mem-8h-memory-bridge.md](./tracks/mem-8h-memory-bridge.md) |
| **MEM パイプライン** | 運用+未 | [architecture/mem-pipeline.md](./architecture/mem-pipeline.md) |
| **OBS** | 📋 | [tracks/obs.md](./tracks/obs.md) |
| **CAM** | 💤 | [tracks/cam-tapo-ptz.md](./tracks/cam-tapo-ptz.md) |
| **EAR** | 📋 | [tracks/ear.md](./tracks/ear.md) |
| **VIS** | 💤 | [tracks/vis-health.md](./tracks/vis-health.md) |
| **GAPI** | ✅ prep-1/2 · **2b/2r/2r-S2/2s** ma-home E2E · 📋 7c/7d | [tracks/gapi.md](./tracks/gapi.md) · [ops/gapi-setup.md](./ops/gapi-setup.md) |
| **TEMP** | 🔧 utterance anchoring + 段階分類 POC | [tracks/utterance-anchoring.md](./tracks/utterance-anchoring.md) · [prottypemarkdown.md](../prottypemarkdown.md) |
| **V / Surface UI 残** | 部分済 | [tracks/surface-vision.md](./tracks/surface-vision.md) |
| **Surface direct LLM** | ✅ v0 + 8h-A/C（compact transcript · memory bridge） | [tracks/surface-direct-llm.md](./tracks/surface-direct-llm.md) · [mem-8h-memory-bridge.md](./tracks/mem-8h-memory-bridge.md) |
| **BIO-8** | ✅ | [heartbeat-loop.md](./architecture/heartbeat-loop.md) § Somatic |
| **Outbound** | ✅ | [architecture/outbound-channels.md](./architecture/outbound-channels.md) |
| **SOUL-D** | 💤 距離感 · 友人化 · Say動機 | [tracks/soul-distance.md](./tracks/soul-distance.md) |
| **プラットフォーム** | ✅ | [architecture/platform-ma-home.md](./architecture/platform-ma-home.md) |

## ADHD body double（構想 · 2026-07-07）

**状態**: 💡 構想段階（すぐ実装しない · ゆっくり熟成）

こより＝まーの **body double**（デスクトップで脱線にそっと気づいて一声かける相棒）。まーが ADHD であるという属性から生まれた発想（隠している属性ではなく、そこから来る必要）。

- **方針**: 監視官ではない（距離語・Say条件は未決 → [soul-distance.md](./tracks/soul-distance.md)）。[VISION.md](./VISION.md) の関係性前提と後で揃える（監視・強制はしない）
- **技術の当たり**: 主役は **前景ウィンドウ/プロセス名検知**（Win32 · 軽量・確実・日本語問題なし）。**OCR は補助**に降格。Unlimited-OCR は日本語 OCR で撃沈（2026-07-07 実測）→ この路線に依存しなくて正解。将来 OCR が要る場合は日本語強い VLM（Qwen2.5-VL 等）を別途評価
- **進め方**: [obs-tick-encode.md](./tracks/obs-tick-encode.md) と同じ **measure-first**。Phase 0＝脱線パターンをログるだけ → データを見てから介入設計。介入は boundary / cadence / quiet hours / OFF 可能とセット（うるさい見守りは逆効果）
- **未決（熟成対象）**: 「脱線」の定義、声かけの強度と頻度、こよりの人格での言い方、プライバシー境界

## RP — 人格の基底化

| Phase | 内容 | 状態 |
|-------|------|------|
| 0–1 | SOUL.core + LM Studio system | **済** |
| 2 | persona LoRA + JSONL export | **2a 済** · **学習は保留**（表層会話がもっと溜まってから） |
| 3 | arc → SOUL（MEM-6） | 未 |

→ [ops/role-persistence-ma-home.md](./ops/role-persistence-ma-home.md) · VIS 間接視覚は [vis-health.md](./tracks/vis-health.md)

## 大阪弁（表層・TTS）

| トラック | 内容 | 状態 |
|---------|------|------|
| **文法 Tier 0** | へん/ひん rewrite | ✅ [osaka-grammar-data.md](./tracks/osaka-grammar-data.md) |
| **イントネーション Tier 2** | accent_phrases seed | 💤 [osaka-accent-intonation.md](./tracks/osaka-accent-intonation.md) |
| **AIVMX 実験** | SBV2 → `.aivmx` | 💤 [aivis-koyori-aivmx.md](./tracks/aivis-koyori-aivmx.md) |

## WS — Web

| ID | 読む場所 |
|----|----------|
| WS-1〜2c | [ops/ws-2-conversation-web-search.md](./ops/ws-2-conversation-web-search.md) |
| WS-2d PDF 抽出（実装済） | [ops/ws-2-conversation-web-search.md](./ops/ws-2-conversation-web-search.md#ws-2d--pdf-抽出実装済-2026-07-07) |
| **DOC-READ** 長文書の読解・議論 | A/B/C/D ✅ · E 📋 | [tracks/doc-read-discuss.md](./tracks/doc-read-discuss.md) |
| WS-5 自発検索 | [ops/ws-5-spontaneous-search.md](./ops/ws-5-spontaneous-search.md) |
| **MEM-8g** | compose salience · gist retire | 💤 v0 · 📋 v1 | [tracks/compose-topic-retire.md](./tracks/compose-topic-retire.md) |

## 運用スクリプト

→ [ops/scripts-reference.md](./ops/scripts-reference.md)

---

## 本番: Keychron K4 MAX Bluetooth

→ [ops/koyori-input-sharing.md](./ops/koyori-input-sharing.md)

## キオスク URL

既定 **presence-ui `:8090`**（8080 直結ではない）。

```bash
cd ~/src/embodied-claude/scripts/koyori-kiosk
sudo ./install-koyori-kiosk.sh
```

`http://ma-home.local:8090/?kiosk=1`

## Input Leap — 済（V5）

→ [ops/koyori-input-sharing.md](./ops/koyori-input-sharing.md) · [ops/koyori-kiosk-ime.md](./ops/koyori-kiosk-ime.md)

診断: `check-koyori-stack.ps1`（ma-home）

## タッチキーボード（onboard）— 保留

`KOYORI_ONBOARD=1` / `apt install onboard`
