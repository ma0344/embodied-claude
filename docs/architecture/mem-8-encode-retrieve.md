# MEM-8 — encode / retrieve 非対称

**合意**: 2026-06-21（まー — [Qiita 記事](https://qiita.com/hatsukaze/items/192403c9ff6a433fe0b6) を契機）  
**地位**: 記憶設計の **判断軸**。実装 umbrella の完了ではない。  
**関連**: [cognitive-layers.md](./cognitive-layers.md)、[heartbeat-loop.md](./heartbeat-loop.md)  
**全文・実例・昇格パイプライン**: [archive § MEM-8](../archive/backlog-ma-home-full-2026-06-26.md#mem-8--encode--retrieve-非対称合意-2026-06-21)

---

## 核心的 tension

> **「後で思い出す価値があるか」は、思い出すときにしか本当は決まらない。**  
> それなのに多くの RAG は **encode 時に一度フィルター** する。

結果:

- encode 時の「重要」≠ retrieve 時の「必要」→ 記憶はあるのに使われない
- フィルターで落とした材料は二度と検索に乗らない → breadth が薄い
- 生ログ全部もダメ（ノイズ・Lost in the Middle）

**対策は retrieve 単体のチューニングだけでは足りない** — 多視点 encode・用途別 retrieve・L0 表層の常備がセット。

---

## 原則（妥協点の方向性）

| 原則 | 意味 |
|------|------|
| **削除より振り分け** | 捨てず **層・kind・チャンネル** へ（digest / inner voice 分割など） |
| **多視点 encode** | 同一出来事を fact / narrative / hook で **別レコード**（8a） |
| **用途別 retrieve** | compose / recall / follow-up で **引く形を変える**（8b） |
| **生ログの最低 1 層** | WM / JSONL / STM 原文を監査用に一定期間（MEM-7） |
| **昇格は遅延判断** | STM は広め — promote されない＝不要 ではない（8c） |

認知層との対応 → [cognitive-layers.md § MEM-8](./cognitive-layers.md#mem-8encode--retrieve-非対称との接続)。

---

## 多段階想起（L0–L4）

```
[L0 表層]  gist / 気配 / 直近 STM     … compose に載せやすい（広く浅い）
[L1 索引]  episode_close / open_loop … 検索の入口
[L2 能動]  recall / divergent / 8b   … 「思い出そう」ときだけ深掘り
[L3 原文]  JSONL / STM 未昇格       … 経緯・逐語（MEM-7）
[L4 再固定] Dreaming / consolidate   … 夜間・稀
```

- **L0–L1** は「重要 fact 自動注入」と逆 — **浅い層を先に常備**、詳細は L2 以降
- **L2** ＝ まーの「思い出そうとしなければ出ない」に相当
- 人間と違って L4 を毎晩回してもよいが、**L0 自動 + L2 能動** の分離は手本と整合

---

## ベクトル検索の限界（設計上の注意）

Chroma `/recall` は embedding 類似。**短い fact が長い episode に負ける**ことがある。

| 現象 | 例 |
|------|-----|
| episodic が fact を押し出す | `recall("ここっち")` が転写ばかり |
| 短い fact が索引に弱い | GH 名の LTM 行 |
| 同音・指示語 | 「ここっち」↔ 口語の「こっち」 |
| 時間 fact の埋没 | スケジュールが episode 要約の 1 行に |

→ **8a** 多視点 fact 行、**8b** query 整形、**8e** `[person_profile_gists]`（暫定 L0）、**8d** L0/L2 整理。

---

## 取り入れる発想（外部考察 · 2026-07-06）

MAGMA 系・長期記憶の一般論・Recall 型アーキテクチャなどは、多くが **retrieve 側の構造化**（類似検索をやめ、時間・因果・実体で辿る）から入る。**encode / retrieve 非対称**は薄いことが多い — まーとの議論（2026-07-06）で整理した、**名前を借りずに取り込める核**だけここに置く。

### 二層設計（MEM-8 の上位に置く）

| 半分 | やること | ma-home への写像 |
|------|----------|------------------|
| **encode** | 解釈を先送り。広め・遅延・振り分け | L3 原文（MEM-7）· 8a 薄い fact 複数 · OBS-TICK（ルーティンは look のみ）· salience 時だけ濃く encode |
| **retrieve** | 問いの型で索引を選ぶ。top-k 一本にしない | 8b 拡張 · calendar の経路分岐と同型の **recall router**（未） |

「きれいな要約を encode 時に確定」は **どちらの半分でも片手落ち**。外部記事の「夜間 semantic 昇華だけ」は、8c（昇格遅延）と L3 が無いと非対称と戦う。

### encode 側で借りること

| 発想 | 意味 | 注意 |
|------|------|------|
| **解釈の先送り** | 記銘はローデータ or ポインタ + 軽い索引。意味確定は想起時 | VLM caption 毎回は **強いフィルタ**（tick・remember 経路） |
| **多レンズ** | 1 本要約ではなく fact / hook を **別レコード**（8a） | 各レンズも「確定解釈」にしない。フック + L3 へのリンク |
| **モダリティ別 cold** | テキスト JSONL は安い。画像はキーフレーム + TTL | `save_visual_memory` の base64 全同梱は重い。角度+時刻+path で足りることが多い |
| **変化時だけ濃く** | **ベースラインからの逸脱**があるときだけ describe / remember | OBS-TICK-1 — 天井固定 · `room_baseline` 相対 |
| **再固定化** | 想起・訂正後に索引を更新 | `interpretation_shift`・まーの訂正。**自動因果抽出はしない**（誤リンクが固定化される） |

### retrieve 側で借りること

| 発想 | 意味 | 既存の芽 |
|------|------|----------|
| **チャンネル分離** | semantic / temporal / entity / causal を **混ぜて top-k しない** | Chroma · social events · episode · `link_memories` · `person_model` |
| **辿る vs 並べる** | 「なぜ」「いつから」は辺・時系列。類似度ランキングだけでは足りない | `get_causal_chain` · `recall_with_associations` — compose 本線は未使用 |
| **entity 先刺し** | 誰・何の話か固定してから semantic | relationship · 8e gists · joint-attention |
| **temporal 索引** | `ts` をメタではなく **第一検索軸**に | events · scene_parse · OBS-TICK-0 後は部屋の semantic 行が減る分、こちらが相対的に重要 |
| **二段 pull** | 索引で当たり → 足りなければ L3・画像・その場 see で再解釈 | VIS-SD（会話 multimodal）· MEM-7 原文 |

### 採用しない（当面）

- encode 時の **単一 VISION_CAPTION** を記憶の正本にする（tick 本線 — OBS-TICK-0 で停止実験中）
- 画像の **恒久・全量**保存と base64 DB 同梱
- LLM による **因果グラフ自動構築**
- フル **4 グラフ常時同期**（コスト・GIGO・レイテンシ）

### 実装への当てはめ（優先の目安）

1. **recall router** — 時間 / 人物 / デフォルト semantic（calendar Stage1 と同型の軽い分岐）
2. **8a** — 1 出来事から fact 行を明示分離
3. **MEM-7** — JSONL 原文層（二段 pull の cold 側）
4. **OBS-TICK-1** — ベースライン相対差分 POC → [obs-tick-encode.md](../tracks/obs-tick-encode.md)

関連トラック: [obs-tick-encode.md](../tracks/obs-tick-encode.md)

---

**ここっち事例（2026-06-25）**: 訂正後に 8e v0 で gist/LTM。残課題は 8a・8d。詳細 → [アーカイブ § MEM-8e](../archive/backlog-ma-home-full-2026-06-26.md#mem-8e--自己開示の広い-encode合意-2026-06-23)。

---

## 実装 ID と状態（2026-06-26）

| ID | 内容 | 状態 |
|----|------|------|
| **MEM-8** | 本ドキュメント＋アーカイブ節 | ✅ **概念済** |
| MEM-8a | 多視点 encode（fact / narrative / hook 分離） | **未** |
| MEM-8b | 用途別 retrieve（compose / recall / follow-up） | **v0 済**（`recall_query`、schedule pin） |
| MEM-8c | 昇格と忘却の分離 | **未** |
| MEM-8d | L0 gist 自動 vs L2 能動 recall の API/UX | **未** |
| MEM-8i | structured retrieve / recall router（時間・人物・semantic 分岐） | **概念**（§ 取り入れる発想） |
| MEM-8e | 自己開示の広い encode | **v0 済** |
| MEM-8f | 「覚えておいて」保管 vs follow-up | **v0 済**（OL-ARCHIVE） |
| **MEM-8g** | compose topic retire — [compose-topic-retire.md](../tracks/compose-topic-retire.md) | **v0 運用確認** · **v1 gist** 📋 |
| **MEM-8h** | cue-driven memory bridge — [mem-8h-memory-bridge.md](../tracks/mem-8h-memory-bridge.md) | **A–D ✅** |
| **OBS-TICK** | 自律 tick 視覚 encode — [obs-tick-encode.md](../tracks/obs-tick-encode.md) | **0 🔥** · **1 📋 草案** |

**関連だが別 ID**

| ID | 内容 | 状態 |
|----|------|------|
| MEM-5k | daybook 要約が薄い（digest/inner_voice を合成に渡す） | **未** |
| MEM-7 | JSONL ライフサイクル（hide≠削除） | **未**（MEM-3 後が安全） |
| MEM-6 | Deep 昇格（arc → SOUL 提案） | **未** |

---

## MEM-8b-lite — compose 注入 tier（運用知識）

**問題（2026-06-25）**: lite compose cap で retrieve 済み fact が LLM 前で切れる（「ねっとわん いつ」 hedging）。

| Tier | 内容 | 扱い |
|------|------|------|
| 0 | `[Must include]` / `[Must avoid]` / `[Social move]` | cap **対象外** |
| 1 | `[schedule_facts]` / top `[relevant_memories]` | compose **先頭 pin** |
| 2 | gists / desires / contract | compose 本体 |
| 3 | `session_history` / `[stm_recent]` | **先に切る** |

**上限（`context_limits.py`）**: `PRESENCE_LITE_COMPOSE_MAX_CHARS=8000`、`PRESENCE_LITE_APPEND_MAX_CHARS=12000`。

**次の実験**: `PRESENCE_TEMPORAL_SCHEDULE_CONTRACT=0` で退縮 → **8d** `answer_facts`。

---

## MEM-8f — 「覚えておいて」線引き（要約）

| 系統 | open loop |
|------|-----------|
| **A. 保管**（必要なとき recall） | **作らない** |
| **B. 継続** follow-up | 作る |
| **C. 時刻付き** | commitment 経路 |

v0: OL-ARCHIVE 1+2（`relationship_mcp.inference.is_archive_remember_utterance` 等）。  
OL-GATE（挨拶・ phatic）とは別問題 — [open-loops-reminders.md](./open-loops-reminders.md#ol-gate)。

---

## 次に着手するなら（優先案）

1. **8g v1** — compose topic retire gist 本線 → [compose-topic-retire.md](../tracks/compose-topic-retire.md)
2. **8a** — 1 episode から fact 行を明示分離（ここっち型の再発防止）
3. **8d** — L0 `answer_facts`、毎ターン全文 recall 禁止の整理
5. **MEM-5k** — daybook 表層を digest から厚くする（ALIVE / 自己要約に効く）
6. **MEM-7** — JSONL 退避（MEM-3 Dreaming 後）

---

## 手本について

人間の記憶を **第一の参照** にしてよいが、**同じである必要はない**。検索インデックス・夜間バッチ・明示 `remember` は生物にない経路。MEM-8 の原則（非対称・多視点・振り分け）は手本に **拘束されない**。
