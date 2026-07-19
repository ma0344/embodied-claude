# docs/ — 読み方ガイド

embodied-claude（ma-home / こより）の運用・設計ドキュメント。**まずここから**。

---

## いつ何を読むか


| 状況                              | 読むもの                                                                                                                    |
| ------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| **いま何をすべきか**                    | [backlog-ma-home.md](./backlog-ma-home.md)（ダッシュボード）                                                                     |
| **なぜこのプロジェクトか**                 | [VISION.md](./VISION.md)                                                                                                |
| **MCP・設備の使い方**                  | [CLAUDE.md](../CLAUDE.md)（リポジトリ直下）                                                                                      |
| **青空読書・生きてる感**                  | [tracks/alive-lw-read.md](./tracks/alive-lw-read.md)                                                                    |
| **自発性（内面拡充 · 指示待ちしない把握）** | [tracks/spontaneity.md](./tracks/spontaneity.md)                                                                        |
| **黙考ルート（GW-S1）**                | [tracks/gw-silent.md](./tracks/gw-silent.md)                                                                            |
| **Gateway / 自律 tick の設計**       | [architecture/gateway-direct-actions.md](./architecture/gateway-direct-actions.md)                                      |
| **Surface Direct（表層 LM 直叩き）**   | [tracks/surface-direct-llm.md](./tracks/surface-direct-llm.md)                                                          |
| **跨 session 記憶 bridge（MEM-8h）** | [tracks/mem-8h-memory-bridge.md](./tracks/mem-8h-memory-bridge.md)                                                      |
| **Heartbeat・pulse**             | [architecture/heartbeat-loop.md](./architecture/heartbeat-loop.md)                                                      |
| **認知層・設計方針**                    | [architecture/cognitive-layers.md](./architecture/cognitive-layers.md)                                                  |
| **注入の層（表層 / 近表層 / Deep）**     | [architecture/inject-surface-layers.md](./architecture/inject-surface-layers.md)                                        |
| **regex / e4b / Stage の使い分け**   | 下 § [regex を使うべきか](#regex-を使うべきか) · [utterance-anchoring.md](./tracks/utterance-anchoring.md)                           |
| **相対日・deixis / TEMP**           | [tracks/utterance-anchoring.md](./tracks/utterance-anchoring.md)                                                        |
| **open loop / リマインド / close**   | [architecture/open-loops-reminders.md](./architecture/open-loops-reminders.md) · [tracks/ol5.md](./tracks/ol5.md)       |
| **MEM-8 / 記憶パイプライン**            | [mem-8-encode-retrieve.md](./architecture/mem-8-encode-retrieve.md) · [mem-pipeline.md](./architecture/mem-pipeline.md) |
| **運用スクリプト**                     | [ops/scripts-reference.md](./ops/scripts-reference.md)                                                                  |
| **キオスク・Surface 運用**             | [ops/](./ops/) · [backlog-koyori.md](./backlog-koyori.md)                                                               |
| **LM Studio / KV**              | [ops/lmstudio-kv-cache.md](./ops/lmstudio-kv-cache.md)                                                                  |
| **セッション引き継ぎ**                   | [handoffs/](./handoffs/)                                                                                                |
| **過去の完了項目**                     | [backlog-archive-ma-home.md](./backlog-archive-ma-home.md)                                                              |


---



## regex を使う判断基準

**正本は分散している** — まず [cognitive-layers.md](./architecture/cognitive-layers.md)（層の分離）と [utterance-anchoring.md](./tracks/utterance-anchoring.md)（TEMP / Stage）を当てる。OL 完了・WS ゲート等の個別メモは各トラック doc。

### 人語解析に極力使わない

- regex は **揺れのない機械的パターン**向き（コード · 限定語彙 · DB）で強い
- **予測不能な自然言語**とは相性最悪
- 「正規表現で人語をカバーできる」は **幻想**

合意: 2026-06-25（GAPI-2s `calendar_read_search` の教訓）。構造化抽出・分類は **e4b / Stage LLM**、regex は deterministic な境界（パス · ID · 既知フォーマット · e4b 呼び出しゲート）に限定。

### 使う（有限・決定的）


| 用途                           | 例                                                 | 詳細                                                                                                      |
| ---------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| **カレンダー日**（意味解釈なし）           | 明日 · N月N日 · 来週火曜 → TEMP-C4                        | [utterance-anchoring § TEMP-C5](./tracks/utterance-anchoring.md#temp-c5--clock--相対時刻アンカー設計--2026-06-29) |
| **e4b / Stage 2 を呼ぶかの軽いゲート** | `午前|午後|\d{1,2}時` · clock っぽい when                 | [§ 相対マーカー / regex の役割](./tracks/utterance-anchoring.md#相対マーカーを増やし続けない)                                  |
| **定番 stock ルート**             | 「明日の予定」→ calendar_read（bridge 禁止）                 | [mem-8h § Stage 1](./tracks/mem-8h-memory-bridge.md#b--stage-1-ルート分岐済)                                  |
| **決定的パース**                   | until 時刻 · prompt fence · 鍵括弧 1 組（GAPI search 予備） | [gapi.md](./tracks/gapi.md) · [stage1-loop-routing.md](./tracks/stage1-loop-routing.md)                 |
| **汚染リスクの低い検出**               | URL · `?` corrupt caption · quiet_hours           | [cognitive-layers § 表層にやらせてはいけない](./architecture/cognitive-layers.md#2-表層にやらせてはいけないこと)                  |




### 使わない / 増やさない


| 案                                  | 理由                    | 詳細                                                                                              |
| ---------------------------------- | --------------------- | ----------------------------------------------------------------------------------------------- |
| **verb / 完了フレーズ regex の増殖**        | 終わりがない · 誤 close      | [stage1-loop-routing.md](./tracks/stage1-loop-routing.md) — **allowlist + Stage1**、blocklist 禁止 |
| **相対時刻マーカーの列挙**                    | この後 / あとで / 今夜 … 文脈依存 | [utterance-anchoring § 相対マーカー](./tracks/utterance-anchoring.md#相対マーカーを増やし続けない)                  |
| **bare greeting 正規表現の拡張**          | 入口の無限リスト              | [utterance-anchoring § やらない方針](./tracks/utterance-anchoring.md#やらない方針)                          |
| **regex 1 本で DB 書き込み**             | 構造が落ちる · 監査不能         | Stage 化 — [§ Stage 2 を増やす判断ルール](./tracks/utterance-anchoring.md#stage-2-を増やす判断ルール)              |
| **表層 LLM / regex で shift・fact 確定** | DB 汚染 · 誤ルーティング       | [interpretation-shift-routing.md](./tracks/interpretation-shift-routing.md)                     |
| **topic / lexicon の regex フィルタ**   | lexicon 地獄            | [compose-topic-retire.md](./tracks/compose-topic-retire.md) — 部分一致 `topic in content`           |




### 判断の短い式

1. **DB が汚れる・捏造が許されない** → 表層にも単純 regex にも賭けない → **Stage 1→2→3 または allowlist コード**（[cognitive-layers](./architecture/cognitive-layers.md)）
2. **有限 · テスト可能 · 欲しい部分を一発で取れる**（「想定外」が起きない）→ regex / コード OK
3. **列挙が終わらない · 文脈依存** → regex は **ゲートまで**。意味は **e4b 単発**（TEMP-C5 / GAPI-7d / OL7 と同型）
4. **1 発 regex/JSON で構造が落ちる**（複合予定 · old→new）→ **Stage 2** を増やす（[S2-1〜S2-7](./tracks/utterance-anchoring.md#stage-2-を増やす判断ルール)）

---

```
docs/
├── README.md                 ← このファイル
├── VISION.md                 プロジェクトの「なぜ」
├── backlog-ma-home.md        ダッシュボード（~150行）
├── backlog-archive-ma-home.md  完了一覧
├── backlog-koyori.md         トピック索引（こより端・記憶・カメラ等）
│
├── tracks/                   トラック仕様（進行中 + 計画済）
│   ├── alive-lw-read.md
│   ├── gw-silent.md
│   ├── ol5.md
│   ├── k-self-code.md
│   ├── vis-health.md
│   ├── obs.md
│   ├── cam-tapo-ptz.md
│   ├── ear.md
│   ├── gapi.md
│   ├── utterance-anchoring.md
│   ├── surface-vision.md
│   ├── surface-direct-llm.md
│   └── mem-8h-memory-bridge.md
│
├── architecture/
│   ├── cognitive-layers.md       設計方針の正
│   ├── platform-ma-home.md       8080・A様子見
│   ├── mem-8-encode-retrieve.md
│   ├── mem-pipeline.md
│   ├── outbound-channels.md
│   ├── gateway-direct-actions.md
│   ├── heartbeat-loop.md
│   ├── intent-bucket-flow.md
│   └── open-loops-reminders.md
│
├── ops/                      運用手順・ハードウェア・LM Studio
│   ├── koyori-input-sharing.md
│   ├── koyori-kiosk-*.md
│   ├── lmstudio-*.md
│   └── ...
│
├── handoffs/                 セッション引き継ぎ（1枚 + Linksee）
├── archive/                  旧バックログ全文・決定記録・セッション export
└── tmp/                      一時ログ（コミットしない想定）
```

---



## tracks/


| ファイル                                                        | 内容                                 |
| ----------------------------------------------------------- | ---------------------------------- |
| [alive-lw-read.md](./tracks/alive-lw-read.md)               | 北極星・LW-READ                        |
| [spontaneity.md](./tracks/spontaneity.md)                   | 自発性二軸・目的別動機・KJ的思考           |
| [gw-silent.md](./tracks/gw-silent.md)                       | 黙考・OL-GATE                         |
| [ol5.md](./tracks/ol5.md)                                   | 予定消化 loop close                    |
| [k-self-code.md](./tracks/k-self-code.md)                   | 自己コード（将来）                          |
| [vis-health.md](./tracks/vis-health.md)                     | VL health・間接視覚                     |
| [obs.md](./tracks/obs.md)                                   | `/observe` フェーズ化                   |
| [cam-tapo-ptz.md](./tracks/cam-tapo-ptz.md)                 | Tapo PTZ 調査                        |
| [ear.md](./tracks/ear.md)                                   | Surface マイク・環境音                    |
| [gapi.md](./tracks/gapi.md)                                 | Google Calendar/Drive              |
| [utterance-anchoring.md](./tracks/utterance-anchoring.md)   | TEMP · 相対日 / uttered_at            |
| [surface-vision.md](./tracks/surface-vision.md)             | V1–V9 UI 残件                        |
| [surface-direct-llm.md](./tracks/surface-direct-llm.md)     | 表層 LM 直叩き · compose/plan intercept |
| [mem-8h-memory-bridge.md](./tracks/mem-8h-memory-bridge.md) | 跨 session 記憶 bridge · stage-1 ルート  |
| [doc-read-discuss.md](./tracks/doc-read-discuss.md)         | 長文書（本・論文）の読解・議論 DOC-READ    |
| [osaka-grammar-data.md](./tracks/osaka-grammar-data.md)     | 大阪弁文法データ・Tier 0 rewrite           |
| [osaka-accent-intonation.md](./tracks/osaka-accent-intonation.md) | イントネーション Tier 2（💤 保留）          |
| [aivis-koyori-aivmx.md](./tracks/aivis-koyori-aivmx.md)     | SBV2→AIVMX 実験手順（💤 アーカイブ）       |


---



## architecture/


| ファイル                                                                  | 内容                     |
| --------------------------------------------------------------------- | ---------------------- |
| [cognitive-layers.md](./architecture/cognitive-layers.md)             | **設計方針の正**             |
| [inject-surface-layers.md](./architecture/inject-surface-layers.md)   | 注入の層 · セッション台本 · ノイズ削減優先度 |
| [platform-ma-home.md](./architecture/platform-ma-home.md)             | 本線・様子見                 |
| [mem-8-encode-retrieve.md](./architecture/mem-8-encode-retrieve.md)   | encode/retrieve 非対称    |
| [mem-pipeline.md](./architecture/mem-pipeline.md)                     | 4層・Dreaming・5e/5f/5k/7 |
| [outbound-channels.md](./architecture/outbound-channels.md)           | 能動届け A4                |
| [gateway-direct-actions.md](./architecture/gateway-direct-actions.md) | gateway 直実行            |
| [heartbeat-loop.md](./architecture/heartbeat-loop.md)                 | pulse・BIO              |
| [intent-bucket-flow.md](./architecture/intent-bucket-flow.md)         | IBF · 受信時ブリーフ（原則 D） |
| [open-loops-reminders.md](./architecture/open-loops-reminders.md)     | OL・OL-GATE             |


---



## ops/ — 運用・ハードウェア


| ファイル                                                                     | 内容                              |
| ------------------------------------------------------------------------ | ------------------------------- |
| [koyori-input-sharing.md](./ops/koyori-input-sharing.md)                 | Input Leap・KB 共有                |
| [koyori-kiosk-browser.md](./ops/koyori-kiosk-browser.md)                 | キオスクブラウザ                        |
| [koyori-kiosk-ime.md](./ops/koyori-kiosk-ime.md)                         | 日本語 IME                         |
| [koyori-near-eye.md](./ops/koyori-near-eye.md)                           | 近眼カメラ                           |
| [koyori-usb-c-recovery.md](./ops/koyori-usb-c-recovery.md)               | USB-C 復旧                        |
| [kiosk-primary-say.md](./ops/kiosk-primary-say.md)                       | キオスク優先発話                        |
| [lmstudio-kv-cache.md](./ops/lmstudio-kv-cache.md)                       | KV cache・Concurrent Predictions |
| [lmstudio-model-change.md](./ops/lmstudio-model-change.md)               | モデル変更手順                         |
| [role-persistence-ma-home.md](./ops/role-persistence-ma-home.md)         | SOUL.core / RP                  |
| [ws-2-conversation-web-search.md](./ops/ws-2-conversation-web-search.md) | 会話 Web 検索 WS-1〜2c               |
| [ws-5-spontaneous-search.md](./ops/ws-5-spontaneous-search.md)           | 自発検索 WS-5                       |
| [scripts-reference.md](./ops/scripts-reference.md)                       | 運用スクリプト早見                       |
| [ma-home-cursor-handoff.md](./ops/ma-home-cursor-handoff.md)             | Cursor 引き継ぎ                     |
| [presence-ui.local.env.example](./ops/presence-ui.local.env.example)     | presence-ui 環境変数例               |


---



## archive/ — 参照用（いま触らない）


| ファイル                                                                               | 内容                   |
| ---------------------------------------------------------------------------------- | -------------------- |
| [archive-index.md](./archive/archive-index.md)                                     | 全文アーカイブ索引・漏れチェック     |
| [backlog-ma-home-full-2026-06-26.md](./archive/backlog-ma-home-full-2026-06-26.md) | 整理前の全バックログ（スナップショット） |
| [c1-native-poc.md](./archive/c1-native-poc.md)                                     | Native PoC 決定        |
| [c2-twicc-decision.md](./archive/c2-twicc-decision.md)                             | twicc 見送り            |
| [mission-A_Investigation-Report.md](./archive/mission-A_Investigation-Report.md)   | ミッション A 調査           |
| [web_ui_design.md](./archive/web_ui_design.md)                                     | 旧 Web UI 設計          |
| `cursor-*` / `session-export-*`                                                    | 長いセッション export       |


---



## handoffs/

短期の作業引き継ぎ。形式は [handoffs/README.md](./handoffs/README.md)。

---



## ステータス記号（backlog 共通）

🔥 進行中 · 📋 次 · 💤 様子見 · ✅ 運用 · 🪦 閉 · 🚫 見送り