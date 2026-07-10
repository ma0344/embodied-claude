# Osaka grammar data sources（こより方言レイヤ用）

**目的**: 標準語ベースの LoRA とは別に、**大阪弁の文法・語彙参照**を compose / SOUL 用に整える。  
**正本の人格語**（お芋さん・飴ちゃん等）は **SOUL** に置く。ここは **公開コーパス・辞書・調査データ** のインベントリ。

**再生成**:

```bash
uv run python scripts/explore_osaka_grammar_data.py
```

出力: `.research/osaka-grammar-data/out/*.json`

---

## 1. 関西弁コーパス（KVJ）— いちばん「今っぽい」

| 版 | 入手 | 大阪向き |
|---|---|---|
| **短単位版 ver.0.9**（推奨） | [NINJAL 2000486](https://repository.ninjal.ac.jp/record/2000486/files/kvjcorpus-suw-0.9.zip) | ファイル ID `KSJ*` = 大阪・神戸都市圏 |
| 生テキスト（インタビュー） | [kvjcorpus](https://sites.google.com/view/kvjcorpus) → KSJ.zip | 利用規約同意後 DL |

- **ライセンス**: CC BY-NC-SA 4.0（非営利・継承）
- **中身**: 若者の身内インタビュー書き起こし。短単位版は UniDic 形態論付き TSV。
- **注意**: KSJ にも京都・兵庫出身話者が混じる（論文 Q1-13 参照）。厳密な「大阪府のみ」ではない。
- **うちの使い方**: `kvj_ksj_patterns.json` — へん／や／あかん 等の **表面形頻度**（規則の自動抽出ではない）

---

## 2. 関西方言 UniDic — 文法が「辞書」になってる

| 項目 | 内容 |
|---|---|
| DL | [UniDic 方言](https://clrd.ninjal.ac.jp/unidic/download_all.html) → `unidic-D-kansai-v202512.zip` |
| 配置 | `.research/osaka-grammar-data/unidic_kansai/`（MeCab 辞書） |
| ライセンス | CC BY-NC-SA 4.0 |

- **MeCab 必須**（`sys.dic` はバイナリ。UTF-8 生読みは不可）
- Windows: [MeCab 本体](https://taku910.github.io/mecab/) + `pip install mecab-python3`
- 手軽確認: [Web 茶まめ](https://chamame.ninjal.ac.jp/) で関西辞書を選択

---

## 3. COJADS — 標準語↔方言の対はある

| 項目 | 内容 |
|---|---|
| URL | https://www2.ninjal.ac.jp/cojads/ |
| 検索 | [中納言](https://clrd.ninjal.ac.jp/chunagon.html) 登録 |
| 無料 | メタ情報付き CSV（サイトのデータ配布案内） |
| 有料 | テキスト XLSX・音声 |

- **大阪地点あり**（1977–85 緊急調査ベース）
- **caveat**: 口語が古い・場面設定談話あり。こよりの「今の大阪」そのものではない。
- **使いどころ**: 標準語句 ↔ 方言表記の **対訳例** を人手で拾うときの参照

---

## 4. 方言文法全国地図（GAJ）— 文法事象のカタログ

| ファイル | 用途 |
|---|---|
| `GAJ_ALL_PointProperty.xlsx` | 地点メタ（大阪府 = **6 地点**） |
| `GAJ23_all_unicode+geocode_202306.xlsx` | 第1調査票（否定 001–015、コピュラ 028 等） |
| `research_item.txt` / `map_item.txt` | 質問文・地図対応 |

- **否定形の大阪回答例**: `gaj_osaka_grammar.json` → `negation.questions.004`（しない → seːhen 等）
- **限界**: 大阪は地点数が少ない。音韻表記（IPA 風）でそのまま compose には使わない。

---

## 5. ローカル参考（Adams Survival Manual）

| ファイル | 備考 |
|---|---|
| `docs/Kansai-ben Survival Manual (Adams Zach 2010).pdf` | 原本（**git 未追跡** · ローカル配置） |
| `docs/KansaibenSurvivalManual_AdamsZach2010_.html` | PDF 変換（**ルビがノイズ** · 同上） |
| `out/adams_plain.txt` | ルビ除去テキスト |
| `out/adams_grammar_index.json` | 章立て + 例語トークン |

- サイト移転: https://kansaiben.com/
- 大阪寄り（関学・大阪神戸ネイティブチェック）だが **教材英語** が主。

---

## 成果物（compose / 12b-qat 用）

| ファイル | 用途 |
|---|---|
| `presets/koyori-osaka-grammar.yaml` | 正本（カテゴリ・std→osaka 対訳・avoid） |
| `presets/koyori-osaka-grammar.distill.md` | **12b system / stable append** に貼る短いカード（〜1k字） |
| `presets/koyori-dialect-lint.json` | e4b / regex 用の敬語漏れヒント（任意） |

**例文プール再生成**（大阪府寄り・若い女性・話者 `*s:` のみ）:

```bash
python scripts/extract_ksj_examples.py
# 既定: %USERPROFILE%/Downloads/KSJ_noPOS → .research/.../out/ksj_examples.json
```

手順のおすすめ順:

1. `explore_osaka_grammar_data.py` — KVJ 頻度・GAJ（根拠データ）
2. `presets/koyori-osaka-grammar.yaml` + `distill.md` — 人手キュレーション正本
3. `extract_ksj_examples.py` — YAML の `corpus_examples` 更新用候補
4. `distill.md` を LM Studio system か SOUL.core 末尾に追記（まー判断）

**COJADS** — 採用しない（口調が古い）。**UniDic 本番導入** — 不要（KVJ 短単位 TSV で品詞付き）。

### Gateway 配線（2026-07-10）

| env | 既定 | 効果 |
|---|---|---|
| `PRESENCE_OSAKA_GRAMMAR_IN_APPEND` | `0` | `1` で `distill.md` を stable append に追加（LM Studio に既に貼ってるなら `0` のまま） |
| `PRESENCE_DIALECT_LINT` | `1` | 表層返答に ですます等があれば `dialect lint:` でログ |
| `PRESENCE_DIALECT_LINT_REWRITE` | `0` | `1` で `koyori-dialect-lint.json` の rewrite_hints を表層に適用（ログ: `dialect rewrite:`） |

**ma-home 試行例**（distill を SOUL.core に書いた場合も append=1 で gateway 側 distill を載せる構成可）:

```env
PRESENCE_OSAKA_GRAMMAR_IN_APPEND=1
PRESENCE_DIALECT_LINT=1
PRESENCE_DIALECT_LINT_REWRITE=1
```

`presence-ui` 再起動後、ログに `dialect rewrite:` / `dialect lint:` が出る。

**否定形（へん/ひん）**: い段語幹→ひん、それ以外→へん。`できへん`✖→`でけへん`/`できひん`。rewrite ON 時は `apply_negation_heh_hin_rules` が表層後処理で適用。

| `PRESENCE_OSAKA_GRAMMAR_PRESET_DIR` | （空） | presets 上書きパス |

コード: `presence_ui.gateway.osaka_grammar` · `build_gateway_stable_append()` · `generate_surface_reply()` 後処理。

**YAML 同期**（corpus_examples / adams_chapters）:

```bash
python scripts/extract_ksj_examples.py
python scripts/sync_osaka_grammar_yaml.py
```

### Irodori TTS とイントネーション

大阪弁の **アクセント・イントネーション** は grammar YAML では直せない。

| エンジン | 手段 | 限界 |
|---|---|---|
| **Irodori** | `ref_wav`（koyori.wav）+ 600M `caption`（感情・テンポ） | 方言アクセントの明示制御なし |
| **Aivis / VOICEVOX** | `audio_query` の `pitchScale` / `speedScale`（実装済）· 理論上 `accent_phrases` 編集 | モーラ単位の手入れは未配線。スタイル（話者 ID）切替は可 |

本番は Irodori 本線。イントネーション実験なら **Aivis フォールバック**（`TTS_DEFAULT_ENGINE=voicevox`）の方がノブは多い。

段階的方針（GL_22_16.pdf）→ [osaka-accent-intonation.md](./osaka-accent-intonation.md)

---

## ライセンスまとめ

| データ | 商用 | 派生配布 |
|---|---|---|
| KVJ / UniDic 関西 | NC | SA（継承） |
| GAJ | 研究引用前提 | 要確認（引用・再配布はサイト規約） |
| COJADS | 配布形態による | 登録・契約による |
| Adams PDF | 個人利用教材 | 再配布は著作権に注意 |
