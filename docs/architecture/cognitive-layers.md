# 認知層 — 「脳のどの部分を使うか」で実装を分類する

**合意**: 2026-06-26（まー — GW / KV / MEM-8 議論）  
**地位**: ma-home の **実装判断の正**（新機能・リファクタ・LLM 追加の前に必ず当てる）  
**関連**: [heartbeat-loop.md](./heartbeat-loop.md)、[mem-8-encode-retrieve.md](./mem-8-encode-retrieve.md)、[tracks/gw-silent.md](../tracks/gw-silent.md)

---

## 設計方針（合意 2026-06-26）

### 原則

1. **表層（まーに見えるこより）と裏の処理を混ぜない。** 同じ Gemma ロードでも、resume 付き会話と単発の前頭葉タスクは **別リクエスト**。
2. **いつ・何を・記憶に載せるか** は gateway / compose / plan / ルール（＋必要なら前頭葉 LLM）。**どう言うか** だけ表層。
3. **encode と retrieve は非対称**（[MEM-8](./mem-8-encode-retrieve.md)）。保存時の「重要」≠ 想起時の「必要」。削除より **層への振り分け**。
4. **捏造・DB 汚染は表層に賭けない。** 分類・閾値・prefetch 根拠なしの断言は前頭葉または感覚チャネルで先に確定。
5. **Concurrent Predictions = 1** を前提に、裏 LM は **表返答の後** または **本線の前の直列 prefetch**。

### 実装前の 3 問

| # | 問い | 層の目安 |
|---|------|----------|
| 1 | まーが「こよりの台詞」と感じる必要があるか？ | はい → **表層**（resume + SOUL） |
| 2 | 正解が型・閾値・JSON で決まるか？ | はい → **前頭葉**（ルール優先、足りなければ単発 LLM） |
| 3 | 世界の生データか、身体か？ | はい → **感覚・身体**（HTTP / 別モデル / デバイス） |

内省（SOUL あり・非表示）と解釈・選択（compose/plan）は 1・2 の中間 — [層の地図](#層の地図) を参照。

### 厳格化 vs 柔軟化

| 方向 | やること | 例 |
|------|----------|-----|
| **厳格化** | 表層・CC ツール・ingest 雑ルールから **前頭葉へ降ろす** | OL-GATE、WS prefetch 必須、boundary |
| **柔軟化** | 表層の推論を **単発 LLM** に逃がし、本線は短い根拠だけ読む | URL 要約、query 整形、reminder_spec |

### Heartbeat との接続

```
notice → interpret → choose → act → remember → schedule
         ^^^^^^^^    ^^^^^^   ^^^
         解釈・選択   plan    表層 or 身体直実行
         + 前頭葉（ingest 後 OL-GATE 等）
```

**interpret = GW-SILENT**（内省 + 前頭葉分類）が BIO ループのいまの穴。詳細 → [gw-silent.md](../tracks/gw-silent.md)。

---

設計判断の補助: **人間なら脳のどの部分を使う作業か？**  
Gateway・LM 呼び出し・記憶を **表層の会話** と **裏の処理** に分ける。KV（`f_keep`）もこの地図に乗る。

---

## 層の地図

| 層 | 比喩 | 役割 | 典型実装 |
|----|------|------|----------|
| **表層** | 会話・自己呈示 | まーに見える「こより」。関係・トーン・驚き | native chat + SOUL、`--resume` |
| **内省** | 意識下の独り言 | SOUL あり・非表示・連続性要る | GW-S1 PAUSE（設計済・未配線） |
| **解釈・選択** | 解釈野・小脳 | いつ・何を・黙るか（台詞ではない） | compose / plan（in-process） |
| **前頭葉** | 実行機能・フィルター | 分類・抽出・要約。無人格・再現性 | OL-GATE、reminder_spec、ルール intent |
| **感覚・身体** | 感覚入力・運動 | 世界との接触・デバイス | e4b vision、url fetch、TTS、カメラ、`:18900` |
| **脊髄** | 反射 | 閾値で即反応（考える前） | corrupt 拒否、Qwen reload、quiet_hours |

```
まー
  ↑↓ 表層（Gemma resume）
  │
解釈・選択 ← compose / plan
  │
前頭葉 ← 単発 LLM / ルール（resume なし）
  │
感覚・身体 ← HTTP / 別モデル / MCP 身体
  │
脊髄 ← 監視・即時反射
```

---

## 1. 表層じゃなきゃいけないこと

**まーが「こよりと話してる」と感じる出力だけ。**

| こと | 理由 |
|------|------|
| 最終の返答文・音声（`say` の言い回し） | 関係・トーンは履歴と SOUL に乗る |
| 共感・躊躇・「わからん」と正直に言う | 信頼は表層の振る舞い |
| 解釈が変わったときの言語化（必要なら） | `interpretation_shift` の「自分としての気づき」 |
| 自律行動でまーに届く短い報告 | 人格付きの一言 |

Heartbeat の **「どう言うか」** はここ。`f_keep` を守る価値があるのもこの帯。

---

## 2. 表層にやらせてはいけないこと

### → ルール / コード（厳格・決定的）

| ✖ 表層 | ○ 向き | いま |
|--------|--------|------|
| `また明日！` → open loop | 固定分類 + gateway 後処理 | OL-GATE 予定（`FUTURE_MARKERS` が漏れ中） |
| quiet hours で喋るか | `socialPolicy.toml` + boundary | ✅ |
| 検索語・URL 検出 | `search_prefetch` / `url_prefetch` | ✅ |
| `?` caption 採用 | `caption_looks_corrupt` | ✅ |
| いつ次に起きるか | `compute_next_pulse` | ✅ |
| remember 永続化 | `:18900` HTTP | ✅ |

**方針**: 間違えると DB が汚れる・捏造が許されない → **表層 LLM に賭けない**。

### → 単発 LLM・前頭葉（柔軟・構造化）

| ✖ 表層 | ○ 向き | いま |
|--------|--------|------|
| `utterance_kind` + スロット抽出 | OL-GATE 単発 | 📋 設計済 |
| ルール外のリマインダー | `reminder_spec` | ✅ |
| 長い URL excerpt の圧縮要約 | 要約プロンプト単発 | 📋 空白 |
| 曖昧な検索 query 整形 | 1 行 JSON 単発 | 📋 WS 後追い可 |

**載せ方**: `/v1/chat/completions`、SOUL なし、resume なし、`[gateway_internal]`。  
詳細 → [gw-silent.md § KV](../tracks/gw-silent.md#kv-を殺さない載せ方ol-gate-vs-lw-read)  
Stage 1/2/3 の増設ルール → [utterance-anchoring.md § Stage 2 を増やす判断ルール](../tracks/utterance-anchoring.md#stage-2-を増やす判断ルール)

### → 感覚チャネル / 別モデル

| ✖ 表層 | ○ 向き | いま |
|--------|--------|------|
| 画像→日本語描写 | Qwen（Gemma KV と分離） | ✅ |
| Web 検索・ページ取得 | DDG / httpx prefetch | ✅ |
| カメラ PTZ・録音 | wifi-cam 直 | ✅ gateway |

**方針**: 生データは **材料**。表層が CC ツールで自分で見に行かない（WS-3 方向）。

### → 解釈・選択層（compose / plan）

| ✖ 表層 | ○ 向き | いま |
|--------|--------|------|
| 黙る / defer / private | `plan.primary_move` | ✅ in-process |
| must_avoid / must_include | plan 契約 | ✅ |
| 記憶・関係の束ね | compose + HTTP recall | ✅ |

台詞ではないが `turn_delta` で user 側に載る **グレー帯**。KV は `PRESENCE_KV_STABLE_APPEND` で分離済み。

**注入ブロックの層分け**（表層 / 表層に近い / Deep · セッション台本 ≠ LTM）→ [inject-surface-layers.md](./inject-surface-layers.md)。

### → 内省（表層とも前頭葉とも違う）

| こと | なぜ中間か |
|------|-----------|
| LW-READ **PAUSE** | SOUL 要るがまー向け台詞じゃない |
| 一節の噛みしめ | 体験の意味づけは自分の連続性 |

OL-GATE にも reminder_spec にも載せない。**resume あり・非表示**。

---

## 設計の一言ルール

```
表層     … まーとの関係が載る言葉だけ
内省     … SOUL あり・非表示・resume 可
解釈選択 … compose/plan（事実と方針、台詞ではない）
前頭葉   … 型・閾値・捏造禁止（ルール優先、足りない所だけ単発 LLM）
感覚身体 … HTTP / 別モデル / デバイス
脊髄     … 監視と即時反射
```

| やりたいこと | 厳格化 | 柔軟化 |
|--------------|--------|--------|
| OL-GATE、boundary、prefetch 必須 | 表層・ingest ルールから **前頭葉へ降ろす** | — |
| URL 要約、query 整形 | — | **単発 LLM**、本線は短い根拠だけ |
| interpret 厚くする | — | **GW-SILENT**（内省 + 前頭葉） |

---

## MEM-8（encode / retrieve 非対称）との接続

全文 → [mem-8-encode-retrieve.md](./mem-8-encode-retrieve.md)。

| MEM-8 多段階想起 | 認知層 | encode / retrieve の意味 |
|------------------|--------|--------------------------|
| **L0 表層 gist** | 表層 + compose 注入 | retrieve: 広く浅く **自動**。SOUL・`[stm_recent]`・profile gist |
| **L1 索引** | 解釈・選択 + DB | episode_close / open_loop — **フック**として encode |
| **L2 能動 recall** | 前頭葉（query 整形）+ 感覚（`:18900`） | retrieve: **思い出そうとするときだけ**深掘り（8b v0） |
| **L3 原文** | 脊髄・監査層 | encode: **広く** STM / JSONL。promote されない≠不要（8c 未） |
| **L4 再固定** | 夜間バッチ（Dreaming） | consolidate — 生物より規則的でも L0+L2 分離は手本と整合 |

**多視点 encode（8a 未）** = 同一出来事を **前頭葉で種類分けして別レコード**（fact / narrative / hook）。  
**表層に fact 全文を毎ターン載せる**のも、**encode 時に fact だけ残す**のも、どちらも MEM-8 tension を悪化させる。

### MEM-8 の状態（2026-06-26）

詳細 → [mem-8-encode-retrieve.md](./mem-8-encode-retrieve.md)。ダッシュボードの「MEM ✅」は MEM-5 系パッチを指し、**MEM-8 umbrella の完了ではない**。

| ID | 内容 | 状態 |
|----|------|------|
| **MEM-8** | 概念整理・設計軸 | ✅ **概念済** |
| MEM-8a | 多視点 encode | 未 |
| MEM-8b | 用途別 retrieve | **v0 済** |
| MEM-8c | 昇格と忘却の分離 | 未 |
| MEM-8d | L0 / L2 API・UX 整理 | 未 |
| MEM-8e | 自己開示の広い encode | **v0 済** |
| MEM-8f | 「覚えておいて」振り分け | **v0 済** |

実例（ここっち事例）・8b-lite tier → [mem-8-encode-retrieve.md](./mem-8-encode-retrieve.md)。

---

## 境界がブレている所（改善候補）

| 現状 | あるべき層 | トラック |
|------|-----------|----------|
| ingest `FUTURE_MARKERS` → loop | 前頭葉 OL-GATE | GW / OL-GATE |
| URL excerpt 6k を本線へ直載せ | 前頭葉要約 → 短 prefetch | WS |
| CC `WebSearch` / `WebFetch` | gateway prefetch | WS-3 |
| compose/plan の決定論化余地 | 解釈層のルール増 | IBF / GW |

---

## 関連ドキュメント

| 文書 | 接続 |
|------|------|
| [heartbeat-loop.md](./heartbeat-loop.md) | notice→interpret→choose→act→remember |
| [gw-silent.md](../tracks/gw-silent.md) | interpret 層・OL-GATE・PAUSE |
| [gateway-direct-actions.md](./gateway-direct-actions.md) | 感覚・身体の直実行 |
| [intent-bucket-flow.md](./intent-bucket-flow.md) | 5W1H・バケツ（前頭葉の枠組み） |
| [lmstudio-kv-cache.md](../ops/lmstudio-kv-cache.md) | 表層 KV・Concurrent=1 |
| [mem-8-encode-retrieve.md](./mem-8-encode-retrieve.md) | encode/retrieve 非対称・L0–L4 |
| [open-loops-reminders.md](./open-loops-reminders.md) | OL-GATE・MEM-8f |
