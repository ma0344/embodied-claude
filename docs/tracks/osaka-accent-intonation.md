# Osaka accent / intonation（段階的方針）

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

## 次に現実的なこと（Tier 2）

**高頻度フレーズだけ** PDF からアクセント型を拾い、TTS 用ミニ辞書にする。

- 対象: こよりがよく言う 30–80 句（挨拶・否定・あかん・ほんまやな 等）
- 形式: `presets/koyori-osaka-accent-phrases.yaml`（将来）

```yaml
# 例（福盛記法の要約メモ — 実装は後）
phrases:
  - text: 知らへんわ
    accent: L0+H1  # PDF から写す
  - text: でけへんねん
    accent: ...
```

- **使い道**: Aivis `accent_phrases` 調整の POC（全文生成には載せない）
- **作り方**: 必要な句だけ PDF を目視で引く（一括パースはしない）

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
