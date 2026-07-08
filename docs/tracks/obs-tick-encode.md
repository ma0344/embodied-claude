# OBS-TICK — 自律 tick の視覚 encode（MEM-8 系）

**状態**: 🔥 **OBS-TICK-0 運用中** · 📋 **OBS-TICK-1 草案** · 📋 **OBS-TICK-2b POC 済**（ペア diff 校準）  
**合意**: 2026-07-06（まー — tick caption は MEM-8 と同型のフィルタ · 差分は「デフォルト状態」基準）  
**関連**: [mem-8-encode-retrieve.md](../architecture/mem-8-encode-retrieve.md)、[obs.md](./obs.md)、[gateway-direct-actions.md](../architecture/gateway-direct-actions.md)、[vis-health.md](./vis-health.md)

---

## 運用前提（2026-07-06）

| 項目 | 内容 |
|------|------|
| **部屋カメラ** | Tapo を **天井付近に固定**（今後もこの運用） |
| **視野** | 見下ろし広角 — デスク・床・主要家具が常に同じ画角に入る |
| **外** | USB 外カメラは廃止。`look_outside` / 窓は **Tapo window preset** |
| **模様替え** | 2026-07 にデスク位置変更・カメラ再配置済み — **新しい「部屋のいつもの絵」が要る** |

天井固定により:

- PTZ `look_around` は **廃止**（tick は preset 固定の単一キャプチャ · 1b で実施）
- 視点 ID は **preset ごと**（`window` / `desk` / `dining`）。tick 本線は `dining`。各 view に baseline（1b′ → 下表参照）
- 差分の比較軸を **「直前フレーム」ではなく「その視点のデフォルト状態（ベースライン）」** に置ける

---

## 課題（open）

自律 `observe_room`（約10分 tick）は、2026-07-06 まで次の経路だった:

```
Tapo look_around → 12b neutral caption → remember（:18900）+ agent_observation + scene_parse
```

これは **MEM-8 の「encode 時に一度フィルターする」典型**である。

| 問題 | 内容 |
|------|------|
| **非対称** | 「後で思い出す価値」は retrieve 時にしか決まらないのに、encode 時の 1 本 caption に部屋全体を潰す |
| **超量子化** | 会話の「見て」と違い tick はこよりが喋らないが、**記憶インデックスへの量子化**は同型 |
| **コスト** | 毎 tick で 12b VL（~数十秒）+ Chroma 行増殖 |
| **画像全部** | ファイル／base64 全保持は容量・プライバシー的に嫌。かつ「結局 caption する」なら二重 |
| **画像ベクトル** | memory-mcp の `save_visual_memory` は **テキスト embed + 画像 base64 同梱**。CLIP 型の画質検索ではない → 別設計が要る |

**未解決（OBS-TICK-1 で詰める）**: **「同じ」をどう規定するか**（適応ベースライン昇格の条件）。差分の言語化タイミング（describe / multimodal）は従属。

---

## OBS-TICK-1 — 設計草案：ベースライン相対の差分

**合意方向（2026-07-06 · まー）**: 部屋にはある程度 **決まったデフォルトの見え方** がある。記憶に載せたいのは **「いつもの絵」に対して何が加わったか / なくなったか**。  
**追記（同日）**: カーテン開閉なども **正当な変化** — encode 時に「ノイズだから捨てる」は MEM-8 と矛盾。**変化は DB に残す**。**しばらく同じ状態が続いたら** それを新しいデフォルト（ベースライン）に昇格させる。難所は **「同じ」の規定**。

### なぜ「直前との差分」だけでは足りないか

| 方式 | 捉えるもの | 弱いところ |
|------|------------|------------|
| **フレーム間 diff** | 10 分前から変わったか | 「いつもと違う」が積み上がらない。照明だけゆっくり変わると毎回イベント化しやすい |
| **ベースライン相対 diff** | **いつもの部屋**からの逸脱 | ベースライン更新（模様替え）が要る。照明は別チャンネルで吸収したい |

天井固定なら **1 枚の基準絵**（+ 低解像アンカー）を持てる。tick の仕事は「全景 caption」ではなく **逸脱検出**に寄せられる。

### 二層モデル：イベントログ（速い）とベースライン（遅い）

| 層 | 時間軸 | 役割 | 捨てない |
|----|--------|------|----------|
| **イベントログ** | 速い | baseline からの **遷移** を記録（カーテン・在席・照明含む） | ✅ 変化は切り捨てない |
| **ベースライン** | 遅い | 「いまの通常」参照。 **K  tick 同型** で昇格 | 古い baseline は **履歴** に残す |

```
baseline B0 ──(遷移)──► epoch E1（カーテン開・など）
   │                         │
   │ 毎 tick: vs B0           │ フレーム同士が「同じ」と判定され続ける
   │                         ▼
   │                    K tick 安定
   │                         │
   └──────────────── baseline B1 := E1 のアンカー
                             （B0→B1 は promotion イベントとして DB に残る）
```

- **encode でやること**: 遷移の検出 + 薄い fact（「baseline B0 から視覚的に変化 · score=…」）。カーテンも在席も **同じ扱い**。
- **encode でやらないこと**: 「これは重要でないから remember しない」という **意味判断**。
- **ベースライン昇格**: 「しばらく同じ」＝新しい通常。以降の「加わった/なくなった」は **B1 基準**。

### コア概念（毎 tick）

```
room_baseline (ceiling_home)     … 現在の「いつもの部屋」B_n
active_epoch (optional)          … 直近の遷移後クラスタのアンカー
        │
        ▼ 毎 tick（LLM なし）
current_frame
        ├─ vs B_n ──► deviation_score（ルーティン判定）
        ├─ vs active_epoch / 直前 ──► stability（「同じ」判定）
        │
        ├─ vs B_n: 閾値未満 → L0 unchanged · desire 充足
        │
        ├─ vs B_n: 閾値以上 & 新規遷移 → deviation_event（DB · 1 回/遷移）
        │       └─ 任意: キーフレーム · 薄い fact · describe
        │
        └─ stability: K tick 連続「同じ」→ baseline_promotion (B_n → B_{n+1})
                └─ promotion もイベントとして DB に残す
```

**遷移の重複抑制**: 同じ epoch 内で毎 tick `deviation_event` を量産しない。**エッジ 1 回** + epoch 内は `stable_in_epoch ×m`（compose 用）で足りる。

### 3 層の残し方（仕様のたたき台）

| 層 | 名前 | 中身 | いつ |
|----|------|------|------|
| **A** | 信号 | `view_id=ceiling_home`, `ts`, `deviation_score`, `vs=baseline_id`, 任意 `phash` | 毎 tick |
| **B** | 遷移イベント | `deviation_event`: `from_baseline`, score, `epoch_id`, 薄い fact | baseline からの **エッジ**（遷移ごと 1 回） |
| **B′** | 昇格イベント | `baseline_promoted`: `B_n → B_{n+1}`, `stable_ticks=K` | epoch が K tick 安定 |
| **C** | 原体 | 遷移・昇格時のキーフレーム path + TTL | エッジ / promotion |

**言葉（describe）** と **画像** は排他ではない:

- **数値・イベント** — 常に先（LLM 不要）
- **言葉** — B のあと、必要なら 1 fact 行（8a）。全景段落は書かない
- **画像** — C のポインタのみ。解釈は想起時 multimodal

**「加わった / なくなった」** の **意味確定** は後回しでよい。encode 時に残すのは **いつ（ts）・どの baseline から・どれくらい（score）**。カーテン開閉も在席も **同じイベント型**。

### 「同じ」をどう規定するか（設計の中心）

**「同じ」≠ 意味が同じ**。**視覚的に安定している**という操作定義だけ。候補は併用可。

| 判定 | 定義（案） | 使い道 |
|------|------------|--------|
| **`same_tick`** | `hamming(phash_t, phash_{t-1}) ≤ ε₁` | フレーム間ノイズ除去 |
| **`same_epoch`** | `hamming(phash_t, epoch_anchor) ≤ ε₂` が **K 回 / 直近 M tick** | **ベースライン昇格**の根拠 |
| **`same_baseline`** | `hamming(phash_t, baseline.phash) ≤ ε₃` | ルーティン「いつも通り」· L0 |

**昇格ルール（案）**:

1. `deviation_event` で新 `epoch_anchor` をセット（遷移フレーム）
2. 以降 `same_epoch` が K tick 続く → `baseline_promoted`（B_n → B_{n+1}）
3. 古い baseline と全遷移イベントは **削除しない**（時系列 retrieve 用）

**カーテン例**:

| 時刻 | 出来事 |
|------|--------|
| t0 | baseline B0（閉） |
| t1 | `deviation_event`（B0 から変化 · 開いた）— **残す** |
| t2–t6 | `stable_in_epoch ×5`（毎 tick 新イベントは出さない） |
| t7 | `baseline_promoted` B0→B1（開いた状態が新通常）— **残す** |
| t8+ | vs B1 で unchanged が基本 |

照明だけゆっくり変わる場合: epoch が細かく刻まれるか、ε を調整するかは **POC ログ**で決める。いずれにせよ **encode 時に捨てない**。

**compose との接続**: いまの `[room_view] same scene ×N`（要約テキストのトークン重複）は、将来 **`stable_in_epoch ×N`** または **`unchanged_vs_baseline ×N`**（信号層ベース）に置き換え。

### ベースライン（`room_baseline`）

| フィールド | 意味 |
|------------|------|
| `baseline_id` | 例 `ceiling_home_2026-07-06`（模様替えごとに更新） |
| `set_at` | 基準を置いた日時 |
| `anchor_path` | 低解像 JPEG（監査・再比較用 · TTL 長め） |
| `anchor_phash` | 固定視点比較用 |
| `notes` | 任意 · まーまたは手動メモ（「デスク南側に移動後」） |

**いつ更新するか**:

1. **明示** — 模様替え・カメラ再固定後（2026-07）。初回 B0
2. **適応昇格** — 上記 `same_epoch` + K tick（**本線**）
3. **手動** — gateway / スクリプトで `set_room_baseline`（昇格の上書き）

~~ambient 帯でイベント抑制~~ — **採用しない**（変化はログに残し、通常化は昇格で行う）。

### 未決の問いへの答え（差分前提）

| 層 | OBS-TICK-1 の答え |
|----|-------------------|
| **tick** | 毎 tick 信号（A）。baseline からの **エッジ** で B。epoch 安定で B′ 昇格。ルーティンは L0 のみ |
| **会話** | VIS-SD = **retrieve 時解釈**。会話で分かったこと（「カメラ上げた」）は **言語 fact** を別チャンネルで remember 可。tick 差分とは混ぜない |
| **describe** | エッジで **単枚 describe または OBS-TICK-2b ペア diff**（候補のみ）· 会話は VIS-SD |
| **retrieve** | **遷移 + 昇格の時系列**（B / B′）+ 任意 L3。意味の「カーテン」は想起時に multimodal / describe |

compose の `[room_view] same scene ×N` → **`stable_in_epoch ×N`** / **`unchanged_vs_baseline ×N`**（上記「同じ」判定と接続）。

### POC の最小手順（実装前）

1. 天井固定で **B0 手動登録**（模様替え後）
2. tick: 単キャプチャ → phash · `deviation_score` · **信号だけ** 1 週間ログ
3. ε₁/ε₂/ε₃ · K · M をログから決める（「同じ」の規定）
4. エッジで `deviation_event`、K 安定で `baseline_promoted` を実装
5. エッジで `deviation_event`；任意 **OBS-TICK-2b** ペア diff（下記 POC 参照）

### Pair-diff POC — Gemma-4-12b-qat（手動 · 2026-07-06）

天井固定の実写2枚を LM Studio で比較。実装前の **解像度・限界の校準**。画像の前後順指定は POC では不統一（順序ミスは本節では割愛）。

#### 3 ラウンドの事実

| # | ペアの性質 | **まーが実際に変えたこと** | **12b-qat の主な出力** | 評価 |
|---|-----------|---------------------------|------------------------|------|
| **A** | ~18秒 · 小変化 | テーブル**中央リモコンを削除**のみ。犬は**寝→頭を上げた**（ペットベッド付近） | リモコン「白→黒に置換」、別リモコン出現、クッション微変化。**猫**（誤）。犬の姿勢変化は未検出 | 物体 salience は反応するが **物体・領域がずれる** |
| **B** | A と同画像 · プロンプト強化 | 同上。＋「消失を明示」「犬/人の姿勢に注目」 | 「消えた」文体には改善。犬を**オレンジソファ上**に置いて「消えた」、黄紙横の**黒リモコンが消えた** | **消失語彙**は効く。**姿勢・正しい領域**は効かず |
| **C** | **after を差し替え** · 大変化 | 1枚目＝人なし状態、2枚目＝**まーがソファで横になり犬が寄り添う** | 人物の出現・ソファの犬・クッションずれを**整合的に**記述。1枚目「犬なし」は誤り（ベッドの犬を見落とし） | **大きな在席変化**は拾える。**微細・低コントラスト**は弱い |

#### 12b-qat が捉える「変化」の解像度（仮説）

| 帯域 | 例 | tick で期待してよいか |
|------|-----|---------------------|
| **L — 大域シーン** | 人物がソファにいる / いない | ✅ ペア diff で **候補 fact** として十分 |
| **M — テーブル小物** | リモコン・スマホの有無 | △ 「何か変わった」は分かる。**どの物体か・削除か移動か**は誤りやすい |
| **S — 姿勢・微動** | 犬が寝→頭を上げた（ベッド同色） | ❌ プロンプト強化でも未検出。別チャネル（ROI 差分 / 会話 VIS-SD） |
| **H — 幻** | 猫、ソファ上の犬（実際はベッド） | 候補 fact に **確定で載せない** |

**「違い」の解釈モード**（観測）:

1. **物体インベントリの増減** — テーブル上のリモコン・スマホ（最も強い）
2. **物語的補完** — 空いた場所を別物体で埋める、「置き換え」（プロンプトで「消失」に寄せられるが物体指定はずれる）
3. **大人物・在席シフト** — ソファの人＋犬（C では成功）
4. **同一個体の姿勢変化** — ほぼ未対応（広角・低コントラスト）
5. **安定の宣言** — 家具配置は同じ、は概ね正しい

#### 合意（まー · 2026-07-06）

> **犬の姿勢まで気づく解像度は、いったん要らない。** 広角・距離があるぶん、観察魔にならない。**L〜M 帯（在席の出現/不在 · テーブル付近に変化）** を tick の目標にする。

- **微細な姿勢**（S）→ 会話の multimodal、まーの発話、将来 ROI があれば別途
- **ペットベッド同色** → 「いない」と誤るのは想定内。確定記憶にしない

#### OBS-TICK-2b — ペア multimodal diff（位置づけ）

| 項目 | 内容 |
|------|------|
| **いつ** | phash / baseline から **エッジ（deviation_event）** のときのみ |
| **入力** | `(baseline_anchor または epoch_start, current)` の **2 枚** |
| **プロンプト** | 消失・added/removed 明示 · 推測は弱く · **順序を必ず指定**（先→後） |
| **出力** | **候補 fact**（`confidence=low` 相当）。remember の唯一根拠にしない |
| **必須併用** | L3 キーフレーム2枚 · 信号層 score · 昇格は機械（1c） |
| **期待解像度** | L〜M 帯。S 帯は期待しない |

プロンプトだけでは **領域指定**（テーブル中央 / ペットベッド ROI）まで届かなかった — 実装時はオプション。まずは **粗い候補 + キーフレーム** で足りる。

#### POC からの設計まとめ

```
毎 tick:  phash vs baseline → 信号（A）· desire
エッジ:   deviation_event（B）+ キーフレーム（C）
          └─ 任意 2b: ペア 12b → 候補 fact（L〜M のみ信頼）
K tick 安定: baseline_promoted（B′）— LLM 不要
会話:     VIS-SD — まーが聞いたときの解釈 · S 帯はこちら
```

**やらない**: ペア diff の毎 tick 実行 · 12b 出力の確定 remember · 姿勢レベルの自律監視

### 採用しない（OBS-TICK-1 でも）

- 毎 tick の全景 `VISION_CAPTION` remember
- フル解像度の連続アーカイブ
- encode 時の **重要度フィルタ**（カーテンを捨てる等）
- CLIP 画像ベクトル索引（別 ID · 将来検討）

---

## 方針案（採用前 · 記録用）

**本線候補（D）**: ルーティン tick と記憶 encode を分離する。

1. **欲求充足** — `observe_room` ＝「見回した」でよい。毎回 caption 必須にしない  
2. **記憶** — **ベースラインからの逸脱**があるときだけ encode（→ OBS-TICK-1）  
3. **画像** — キーフレーム + path + TTL（base64 は DB に入れない）  
4. **LLM 条件** — deviation_event または会話トリガー時だけ describe  
5. **会話との分担** — まーが「見て」と言ったときは VIS-SD（12b multimodal 直渡し）。tick は L0/L1 の気配更新

**採用しない（当面）**

- 毎 tick の長い `VISION_CAPTION` remember（現状維持しない）  
- 画像全量の恒久保存  
- 未設計の画像ベクトル索引を「とりあえず」入れること

詳細議論: 2026-07-06 Cursor セッション（VIS-SD / MEM-8 文脈）。

---

## OBS-TICK-0 — 実験（いま）

**目的**: caption 停止の **弊害を運用で観測**する（設計確定前の最小差分）。

| 項目 | OBS-TICK-0 の挙動 |
|------|-------------------|
| `camera_look_around` | ✅ 継続 |
| 12b `describe_existing_capture` | ❌ **停止** |
| `:18900` `remember` | ❌ **停止** |
| `satisfy_desire` `observe_room` | ✅ **キャプチャ成功で充足**（remember 非依存） |
| `agent_observation` | ✅ 最小文のみ（角度数 · caption off 明示） |
| `scene_parse` | ✅ `scene_summary` は最小（caption なし） |

**コード**: `presence_ui.gateway.direct_actions.observe_room_direct`

**影響しうる経路（観測ポイント）**

| 経路 | 期待される変化 |
|------|----------------|
| compose `relevant_memories` | 部屋観察の新規 observation 行が増えない |
| `[room_view]` / 同シーン束ね | 更新が止まる可能性 |
| `recent_experiences` | 「部屋の様子」要約が薄くなる |
| VIS health（既存トラフィック計測） | tick から VL 品質サンプルが減る |
| LM Studio 負荷 | tick あたり VL 1 回減 |

**ロールバック**: 方針案（上）の「変化時 encode」実装時に、describe + remember を条件付きで復帰。

**スモーク**:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/v1/autonomous-tick" -Method POST `
  -ContentType "application/json" `
  -Body '{"smoke_action":"observe_room","trigger":"smoke"}' | ConvertTo-Json
```

（caption なし · **単キャプチャ**のため数秒〜十数秒）

---

## 実装 ID（予定）

| ID | 内容 | 状態 |
|----|------|------|
| **OBS-TICK-0** | caption/remember 停止 · desire のみ | 🔥 **運用中** |
| **OBS-TICK-1** | **ベースライン相対差分** · deviation ゲート · `room_baseline` | 📋 **設計草案** |
| OBS-TICK-1a | baseline 登録 / 更新 API（模様替え後） | **1b に内包**（`ensure_all_baselines`） |
| **OBS-TICK-1b** | tick 単キャプチャ + score ログ（describe なし） | 🔥 **実装済**（2026-07-06） |
| **OBS-TICK-1b′** | **視点(preset)ごと baseline** + 信号に `view_id` 列 | 🔥 **実装済**（2026-07-07） |
| OBS-TICK-1c | **「同じ」判定** · epoch · K-tick `baseline_promoted` | 未 |
| OBS-TICK-2 | 遷移時 MEM-8a 薄い fact 行（機械 score 主体） | 未 |
| **OBS-TICK-2b** | エッジ時 **ペア multimodal diff**（候補 fact · L〜M 帯） | 📋 **POC 済**（手動） |
| OBS-TICK-3 | キーフレーム path + TTL（L3 ポインタ） | 未 |
| OBS-TICK-4 | tick から `look_around` 省略（preset 固定） | **1b で実施**（`capture_for_mode`） |

**1b 合意（2026-07-06）**: 単キャプチャ · 手動 B0 · **人なし**通常状態。

### 1b′ — 視点ごと baseline（2026-07-07 · まー合意）

**問題**: こより自身が `look_outside` で **window preset に向けたまま朝** → 次 tick が窓向きなのに部屋 baseline と比較 → 「向きが変わった」が「部屋が変わった」に化ける。加えて暗視（照明）も混入。

**決定**: **その時点のカメラ向き（preset）ごとに baseline を切り替える**。DB/ログに **`view_id`** 列で「どこ」の変化かを持つ。

| view_id | preset | 経路 | baseline |
|---------|--------|------|----------|
| `window` | 1 | `look_outside` | window B0（外・昼） |
| `desk` | 2 | `look_desk` | desk B0 |
| `dining` | 3 | `observe_room`（**tick 本線**） | dining B0（部屋全景） |

- **tick `observe_room`** は **dining preset に固定移動**してから撮る（`current` の向き曖昧を排除 = OBS-TICK-4 の一部）。こよりが窓/デスクへ向けても tick は必ず dining 基準へ戻る。
- **向き判定**は **action→view_id マップ**が本線（`current` は使わない）。
- baseline 3枚: `~/.claude/presence-ui/baselines/{view_id}_2026-07-07.jpg`、manifest `room_baselines.json`（`view_id → baseline_id / anchor_phash_hex / …`）。
- 信号: `room_scene_signals.jsonl` の各行に `view_id` / `baseline_id`。`last_phash` も view ごと。
- 照明（昼/夜・暗視）は**まだ別軸**。まず視点分離でノイズの大半（窓向き誤比較）を除去 → あとで `*_day` / `*_night` or epoch 昇格（1c）。

**センサー時間ノイズ潰し（2026-07-07 まー観察）**: ライブ画像は物理的に静止していても 1 秒毎に下位ビットが揺れる（dHash `hamming_prev` が静止時も 9〜12）。壁・床など**ほぼ均一な領域で隣接差がノイズレベル**になり dHash の符号がランダム反転するため。対策:
- **前処理 GaussianBlur**（`PRESENCE_ROOM_BLUR_RADIUS`、既定 1.0）で高周波を除去
- **主信号を DCT pHash に**（`phash_dct_hex` / `hamming_dct_*`）。低周波係数のみ見るのでノイズに強い。dHash（`phash_hex` / `hamming_*`）と MAE は比較用に併記
- **観察**: window は `hamming_baseline≈2`（構造一致）でも `mae≈0.17`（外の明るさ差）→ **phash=構造 / MAE=照明** に役割分担。1c の照明軸分離に使える
- コード: `presence_ui.services.room_scene`（`VIEW_IDS` · `ensure_all_baselines` · `log_room_tick_signal(view_id=…)`）· `observe_room_direct`（dining）· `look_preset_direct`（window/desk/dining にも信号）。
- env: `PRESENCE_ROOM_BASELINE_IMAGE_{WINDOW,DESK,DINING}`。preset ID は `wifi-cam-mcp/.env`（`TAPO_*_PRESET`）。
- **開発用フレーム保存**（`PRESENCE_ROOM_SAVE_FRAMES=1`、既定 OFF）: `~/.claude/presence-ui/frames/{view_id}/` に JPG。ファイル名に hamming 埋め込み（`YYYYMMDDThhmmss_b<baseline>_p<prev>_dctb<..>_dctp<..>.jpg`）→ 名前ソートで「跳ねた tick」を目視選別。犬/人/ノイズの切り分け用。view ごと最新 `PRESENCE_ROOM_FRAMES_MAX`（既定 200）のリングバッファ。

### 信号 POC 実測（2026-07-07 夕〜夜 · dining/window）

ブラー＋DCT 投入後の初日実測。**シグナル/ノイズが明確に分離**：

| 状況 | `hamming_prev` | mae | 備考 |
|------|:--:|:--:|------|
| **dining 無人・静止** | **0（4 tick 連続）** | 0.089–0.091 | 真のノイズフロア＝0。mae は微揺れ（実フレームは新規、phash が量子化で同一） |
| **dining 人が入室** | **10–14** | 0.096 | 明確に跳ねる（在席出現 = L 帯） |
| **dining 遷移→定着** | 跳ね → 6 秒後 0 | — | 着席して静止＝新 epoch。1c の「変化して安定」が1回で観測 |
| **dining 食事中（動作）** | 6–14 継続 | 0.096 | 人が動く間は prev が中程度で継続 |
| **window 夜** | baseline 距離 dHash 29 / **DCT 32** | 0.185 | 下記 |

**ε 叩き台（データ根拠）**: `same_baseline`（無人ルーティン）＝ prev≈0 / `deviation`（在席・活動）＝ prev≥7。dining の baseline 距離 14〜17 は「昼・無人からの定常オフセット」で変化ではない。**閾値 5〜7 で誤検出ゼロ・在席検出可**。

**window 昼夜問題（まー説明 2026-07-07）**: window baseline は**昼・カーテン開・庭/縁側が見える**状態で撮影。夜の tick は **暗い＋カーテン閉＋カーテンレールに洗濯物**。照明（明→暗）・構造（カーテン開→閉）・物体追加（洗濯物）の**三重の差**が重なり baseline 距離 32（≒半分）。→ **window は昼夜（＋カーテン状態）で baseline を分ける必要**（`window_day` / `window_night` 等）。dining は当面 baseline 1 本で足りる（昼夜とも 14〜17 に収まる）。
