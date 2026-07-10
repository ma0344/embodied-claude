# Osaka accent / intonation（段階的方針）

**状態**: 💤 **Tier 2 一時停止**（2026-07-10）— AIVMX / SBV2 実験でイントネーション品質が足りず、当面は **Tier 0–1 のみ**（文法 rewrite + Irodori ref 声質）。

**参照**: [GL_22_16.pdf](../GL_22_16.pdf) — 福盛貴弘「大阪方言 2000 文」アクセント（京阪式 H/L 記法）

**結論**: 2000 文を全部ルールエンジン化するのは **非現実的**。文法レイヤ（へん/ひん）と **TTS アクセント** は分離し、**段階的に**足す。

---

## いまやること（Tier 0–1）

| Tier | 内容 | 状態 |
|---|---|---|
| **0 文法** | へん/ひん・でけへん・や | ✅ `presets/koyori-osaka-grammar.*` + rewrite |
| **1 声質** | Irodori `ref_wav` / Aivis 話者・pitchScale | 運用中 |

→ イントネーションの「なんとなく大阪」は **参照声** に任せる。

---

## 次に現実的なこと（Tier 2）— 💤 保留

**2026-07-10**: seed と抽出脚本は残すが、**TTS 配線・AIVMX 実験は再開しない**。ピンポイント句だけ試したくなったらこの doc を参照。

**高頻度フレーズだけ** PDF からアクセント型を拾い、TTS 用ミニ辞書にする。

- 対象: こよりがよく言う 30–80 句（挨拶・否定・あかん・ほんまやな 等）
- 形式: `presets/koyori-osaka-accent-phrases.yaml`（**seed 27 句**）
- 更新: `python scripts/extract_osaka_accent_phrases.py`（pypdf で GL_22_16 から H/L を拾う）

```yaml
# 例（福盛記法 — PDF から抽出）
phrases:
  - text: "あるもんや"
    accent: "L0+H1→L3"
    tag: affirm
  - text: "でけへん"
    accent: "H1"
    tag: negation
```

- **使い道**: Aivis `accent_phrases` 調整の POC（全文生成には載せない）
- **作り方**: seed リストを手で足し、PDF 一致はスクリプト。`TBD` は目視補完

---

## やらないこと（Tier ✖）

- GL_22_16 全 120 ページを LLM プロンプトに入れる
- 毎発話のモーラ列を e4b/12b で生成してから TTS
- 文法 rewrite とアクセント rewrite を同じパイプラインに混ぜる

---

## Aivis vs Irodori（再掲）

| | 文法テキスト | アクセント制御 |
|---|---|---|
| **Irodori** | caption（感情） | ref_wav 依存 |
| **Aivis** | 同一 | `audio_query` → `pitchScale` / 将来 `accent_phrases` |

イントネーション **実験** は Aivis フォールバックが筋がいい。本番 Irodori は ref 改善が先。

---

## 関連

- [osaka-grammar-data.md](./osaka-grammar-data.md) — 文法データ・gateway env
- [irodori-tts-API-for-Python.md](../irodori-tts-API-for-Python.md) — TTS API
