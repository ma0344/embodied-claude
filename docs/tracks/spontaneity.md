# 自発性（SPONT）— 内面拡充と、指示を待たない把握・行動

**状態**: 📋 方針合意（2026-07-17）· **B 軸 concern モデル合意** · 実装 S1 から  
**ダッシュボード**: [backlog-ma-home.md](../backlog-ma-home.md)  
**関連**: [alive-lw-read.md](./alive-lw-read.md)、[heartbeat-loop.md](../architecture/heartbeat-loop.md)（Somatic 対比）、[ol5.md](./ol5.md)、[ws-5-spontaneous-search.md](../ops/ws-5-spontaneous-search.md)、[mem-8-encode-retrieve.md](../architecture/mem-8-encode-retrieve.md)、[soul-distance.md](./soul-distance.md)、[open-loops-reminders.md](../architecture/open-loops-reminders.md)

---

## 要するに（まー 2026-07-17）

自発性を持たせたいのは、だいたいこの **二軸**:

| 軸 | 欲しいこと | 会話相手としての効き |
|----|-----------|---------------------|
| **A. 内面の拡充** | 読書・調べ・観察・内省で、こより側の世界が広がる | **深み / 広がり**（応答マシン感の回避） |
| **B. 指示待ちしない把握・行動** | 「見て／調べて／リマインドして」を待たず、まーの **予定・様子** を把握して動く | **同居する相手**としての気配（うるさくない範囲） |

北極星の「生きてる感」([alive-lw-read.md](./alive-lw-read.md)) は A が第一シーン。B は OL / GAPI / outbound / near-eye / WS-5 にまたがる。

**やらないこと**: 監視・べたつき・毎ターンの用事作り。境界（quiet / `do_not_interrupt` / 在席ゲート）は自発の反対ではなく **前提**。

---

## 動機は目的ごとに違う（合意方向）

「自発性」を一本の数値（`dominant` 勝ち）にすると、外向きが `miss_companion` に寄りやすい。

| 行動の目的 | 動機になりやすいもの | 既存 desire / 経路（仮） |
|-----------|---------------------|-------------------------|
| 内面を広げる | 好奇心・文学・乾きの不快 | `literary_wander` · `browse_curiosity` · `cognitive_load` |
| 観察を自分のものにする | 部屋・外・近傍の変化 | `observe_room` · `look_outside` · near-eye |
| まーの予定・様子を把握する | 続き・未完了・カレンダー | open loop · GAPI · OL6/OL7 · **schedule_concern**（下節） |
| 軽い一声・共有 | 気配・共有したい種 | `miss_companion`（軽い接触）· outbound |
| 会話中の事実確認 | 認知ギャップ・不確かさ | WS-5 / 5b / 5c |

**ブロッカー（まー）**: 面白いアイデアが残るのは、多くが **判断基準の数値化**（目的別の感情チャンネル・閾値）が未決だから。安全側（bool / allowlist）は決めやすいが、動機側はチャンネル別が要る。

→ 実装は「Emotion タグ増殖」ではなく **目的（action class）→ desire / 信号 → 閾値** の三段。詳細は議論メモ（UEC 感情ダイナミクス論文は「合理経路∥感情経路」の参考）。

---

## 項目索引（まーが言ってきた自発性）

### A — 内面拡充（話してない時間にも動く）

| ID | 内容 | 状態 |
|----|------|------|
| LW-2 / LW-READ / GW-S1 | 青空一冊・READ/PAUSE・黙考 | ✅ |
| LW-7 | 読書 → 興味 → Web | ✅ 配線 · 📋 運用確認 |
| LW-6 | memory / open loop から Web 散歩 | 📋 |
| LW-3 | 共有するか黙るか | 📋 |
| LW-5 / MEM-5f | 心の声・「青空読んでる」可視化 | 部分 / 📋 |
| ALIVE-4 | 夜の内側 → 朝 compose | 部分 |
| think_or_discuss | `cognitive_load` 軽い思考 | ✅ 骨格 · 中身薄い |
| observe / OBS-TICK | 定期観察・encode | ✅ tick · 📋 encode |

### B — 指示を待たない把握・行動

| ID | 内容 | 状態 |
|----|------|------|
| **SPONT-B1 (S1)** | 期限過ぎ open loop → `concern` → tick outbound 確認 | 🔧 実装済 · 既定 OFF |
| **SPONT-B2 (S2)** | 自律 tick でカレンダー短冊（Expectation · 喋らない） | 🔧 実装済 · 既定 OFF |
| **SPONT-B3 (S3)** | カレンダー **開始前** nudge のみ（earliness / pre_window · 完了確認なし） | 📋 |
| OL / OL5–OL7 | 予定・約束の把握・close・return-signal | ✅ 多く · OL6 は人間ターンのみ |
| GAPI | Calendar / Drive | ✅ 多く · 📋 残 |
| Outbound / miss_companion | 自律一声（軽い接触） | ✅ トーン調整済 · 💤 距離語 |
| Near-eye | 在席把握（speak ゲート） | ✅ |
| WS-5 / 5b / 5c | 「調べて」無しの事実確認・天気・同意検索 | ✅ v0–5c · 📋 v1 |
| prefetch → 会話 | 調べた結果が台詞に載る | 📋（梅雨例など体感ギャップ） |

### 横断

| 項目 | メモ |
|------|------|
| うるさくない | boundary / quiet / 在席ゲート |
| 判断基準の数値化 | 目的別チャンネル（上節） |
| CC 離脱 | 自発・内面の本線は gateway tick（CC 不要） |

---

## 思考プロセス仮説 — KJ 法的な「短文のつなぎ」（まー 2026-07-17）

### まーの感覚

「考える」は KJ 法に近く、**短めの 1 文**（既知の事実・既に持っている考え）を **つなげていく** 行為。  
LLM 内部はそれより細かい単位だが、**「短い単位を連ねて構造を出す」** 点は近い。

### こよりへの問い

> こよりの記憶を、そのつなぎの材料として思考に使えるか？  
> → 事実や経験の **つながりを広げられる**のでは？

### 設計への当てはめ（仮説 · 未実装）

| 層 | いま | KJ 的に言うと |
|----|------|----------------|
| L0 gist / STM | 浅い常備 | **短冊（カード）の山** — すぐ手に取れる文 |
| L1 open loop / episode | 索引 | **見出し・束ねるフック** |
| L2 recall / divergent | 能動想起 | **意図的に隣の短冊を探す** |
| GW-S1 / PAUSE | 黙考 | **短冊を並べて「いまの解釈」を 1〜数文に固める** |
| Dreaming / overnight | 夜間 | **束の再配置・ラベル付け**（昇格は遅延） |

MEM-8 の原則と矛盾しない:

- encode 時に「重要か」を決めすぎない → 短冊は **多めに残す**（削除より振り分け）
- retrieve 時に「何が必要か」を決める → **つなぐ目的**（内省 / 予定把握 / 会話）ごとに引く形を変える
- ベクトル類似だけでは短い fact が長い episode に負ける → **短文カード化**（8a 多視点・8e gist）が KJ 材料向き

### やりたい形（受け入れの仮）

1. **材料**: 記憶・経験・観察が「1 文〜短い塊」として取り出せる（gist / hook / fact 行）
2. **操作**: 黙考や tick で、目的に応じて数枚を選び **つなぎ文**（解釈・次の一手・共有の種）を出す
3. **成果**: つながった結果が remember / open loop / compose surface に残る（一回限りの独白で終わらない）
4. **非目標**: 巨大コンテキストに生ログを全部載せること · 「考えてる風」の長文テンプレ

### 向きつき短冊ネットワーク（合意 2026-07-18）

**「今している会話」の向きに合う「過去の短冊」を、台詞ではなく材料として辿れるか。**  
ネットワーク化に近いが、巨大知識グラフや因果の自動構築ではない（[mem-8 § 採用しない](../architecture/mem-8-encode-retrieve.md#採用しない当面)）。

| 層 | 役割 |
|----|------|
| **encode** | 向きの付いた短いカードを増やす（例: `まーは直近で〇月〇日に麺類（蕎麦）を食べた記録がある`） |
| **retrieve** | 今セッションの方向と短冊の向きを合わせる（MEM-8h bridge · salience 門番） |
| **表層** | つなぎの一言だけ担当（「この間は蕎麦やんな」） |

会話経路の第一ノード: 食事カード → [mem-8h-memory-bridge.md](./mem-8h-memory-bridge.md)。同 session の台本は [inject-surface-layers.md](../architecture/inject-surface-layers.md) の room transcript が本流。

第一実験の候補（まだ決めない）:

- LW PAUSE: 節の hook + 既存 L0/L1 短冊 → `interest_tags` / `followup_query`（いまの GW-S1 を「つなぎ」明示へ寄せる）
- 会話前: open loop + 直近 gist を短冊として compose に並べ、表層はつなぎだけ担当
- B 軸: カレンダー / loop の短文を並べて「いま把握すべき様子」を 1 文に要約 → outbound 可否は別閾値

---

## B 軸 — 予定への関心と確認（合意 2026-07-17）

**実装順**: **S1 → S2 → S3**（まー合意）。  
**本丸**: 「あれ？」が動機になり「確認しなきゃ」になる変換の数値化。  
**比喩**: [heartbeat-loop.md](../architecture/heartbeat-loop.md) の **Somatic loop**（正常との差分 → 違和感 → 確かめる → 対応）の **対人・予定版**。

### プロセス名（正本）

| 段 | 名前 | 中身 |
|----|------|------|
| 1 | **Expectation** | 予定・期限を知っている（open loop / カレンダー / commitment） |
| 2 | **Temporal trigger** | 時刻が近づく、または過ぎる |
| 3 | **Evidence gap** | 開始・完了の **陽性証拠がない**（欠測） |
| 4 | **Concern appraisal** | 「あれ？大丈夫かな？」— 関心の立ち上がり |
| 5 | **Check intention** | 「確認しなきゃ」— 確認意図の成立 |
| 6 | **Intervention** | 確認行動（outbound / compose 質問） |

**観測変数の注意**: 「まーが行動していない」は監視が要るので **入力に使わない**。コード上は `evidence ∈ {none, weak, positive}`（会話・loop close・明示完了など）。

Gemini 等の「認知的不協和」は本用途には不向き（自分の信念矛盾が中心）。ここは **予測誤差 / 証拠ギャップ × 関心（care）** が近い。OODA は外形メタファーとして可。

### Heartbeat への対応

```
notice    … 期限・loop・カレンダー信号
interpret … Expectation + Evidence gap → concern
choose    … check intention（他 desire / boundary と競合）
act       … outbound 一声 / compose 注入
remember  … 確認時刻・返答・loop 状態
schedule  … 再確認の next_wake（必要時）
```

### 「あれ？」の数値化（v0 式）

```text
evidence_gap ∈ [0, 1]     # none=1, weak≈0.4, positive=0
urgency      = f(lateness) # S1: 期限過ぎ。S3: earliness / pre_window
stakes       ∈ [0, 1]     # 予定種別の粗ラベル（v0 は定数でも可）
care         ∈ [0, 1]     # B 軸チャンネル定数（schedule_concern）

concern = evidence_gap × urgency × stakes × care
```

**「確認しなきゃ」**（意図）:

```text
check_intention ⇔ concern ≥ θ_check
```

**実際の発話**（行動ゲート）:

```text
act ⇔ check_intention
      ∧ quiet_ok ∧ presence_ok（在席・speak ゲート）
      ∧ interruption_cost 低
      ∧ (t_now - last_check_at) ≥ cooldown
```

動機（concern）と行動（act）は分離。うるささは `θ_check` · cooldown · `interruption_cost` で抑える。

### S1 — 期限過ぎ open loop 確認（第一縦スライス）

**状態**: 🔧 実装済（2026-07-17）· 既定 OFF（`PRESENCE_OL6_OUTBOUND=1` で有効）

**いま（人間ターン）**: OL6 は次の人間発話で `[loops_due_for_check]` → plan が自然に聞く。  
**S1（自律）**: autonomous tick で同条件を評価し、`concern ≥ θ` なら **outbound**。

#### 受け入れ（v0）

| 項目 | 値 |
|------|-----|
| evidence | loop が open のまま ⇒ `evidence_gap=1` |
| urgency | 期限過ぎ済み（compose が due）⇒ `1.0` |
| stakes / care | env 既定 `0.8` / `0.8` |
| θ_check | `PRESENCE_OL6_OUTBOUND_CONCERN_THRESHOLD` 既定 `0.5`（concern≈0.64 で発火） |
| ゲート | presence · boundary say · outbound cooldown · **commitment due 優先** |
| 痕跡 | enqueue 成功後のみ `mark_loop_check_asked` |
| 対象 | `trigger=post_deadline_first_turn` のみ（OL7 は ingest） |
| 台詞 | 「まー、{topic} のやつ、もう片付いた？」（決定的 · LLM なし） |

#### env

```powershell
PRESENCE_OL6_OUTBOUND=1
# PRESENCE_OL6_OUTBOUND_CONCERN_THRESHOLD=0.5
# PRESENCE_OL6_OUTBOUND_STAKES=0.8
# PRESENCE_OL6_OUTBOUND_CARE=0.8
```

#### コード

- `presence-ui/.../ol6_outbound.py` — concern · outbound · mark
- `autonomous_tick.py` — plan 後に `maybe_fire_ol6_outbound`
- smoke: `smoke_action=check_open_loop`（在席省略 · due loop が compose に要る）

#### 例シーン

```text
14:20  まー「15時までに申請書」→ open loop（until 15:00）
15:20  tick · 完了なし · concern≥θ · boundary OK
       → 「申請書のやつ、もう片付いた？」
「終わった」→ OL6 pending close（既存）
```

**返答後**: 既存 OL6 close / denial。再確認は `check_asked_at` one-shot（S1 では再スケジュールしない）。

### S2 — 自律カレンダー短冊（知る ≠ 喋る）

**状態**: 🔧 実装済（2026-07-17）· 既定 OFF（`PRESENCE_CALENDAR_LOOKAHEAD=1`）

**原則（まー合意）**: 予定を知っていることと、予定について喋ることは別。  
S2 は **Expectation の供給だけ**。発話は次のときだけ:

| 喋ってよい | 経路 |
|------------|------|
| まーが予定を聞いた | 既存 GAPI calendar prefetch（cue + Stage1） |
| 期限過ぎ確認が必要 | S1 OL6 outbound / concern |
| 明示リマインド due | commitment reminder |

| 喋らない | |
|----------|--|
| tick で見ただけ | `[calendar_expectations — background only]`（**表層に近い** · [inject-surface-layers](../architecture/inject-surface-layers.md)） |
| miss_companion の軽い一声 | must_avoid でカレンダー禁止 |

#### 受け入れ（v0）

| 項目 | 値 |
|------|-----|
| 入力 | tick で Google Calendar `now → now+N hours` |
| 内部 | `~/.claude/presence-ui/calendar_expectations.json` |
| 注入 | compose enrich → compact に background ブロック + `response_contract.avoid` |
| 発話 | **しない**（outbound enqueue なし · must_include にしない） |
| API 抑制 | `PRESENCE_CALENDAR_LOOKAHEAD_MIN_INTERVAL_MINUTES` 既定 30 |

#### env

```powershell
PRESENCE_GAPI_ENABLED=1
PRESENCE_CALENDAR_LOOKAHEAD=1
# PRESENCE_CALENDAR_LOOKAHEAD_HOURS=6
# PRESENCE_CALENDAR_LOOKAHEAD_MAX_EVENTS=5
# PRESENCE_CALENDAR_LOOKAHEAD_MIN_INTERVAL_MINUTES=30
```

#### コード

- `presence-ui/.../calendar_expectations.py` — fetch · cache · inject
- `autonomous_tick.py` — compose 前に silent refresh
- `somatic_context.enrich_interaction_context` — inject
- miss_companion ping: calendar expectations を must_avoid

### S3 — 予定直前 nudge（開始だけ · 終了確認はしない）

**状態**: 📋 方針合意（2026-07-17）· 実装は S1 θ 校准後  
**原則（まー合意）**: 「開始だけ」と「終了確認まで」は **入口の分離**で足す。新しい分類器は v0 では要らない。

| 出どころ | 性質 | 声かけ | 経路 |
|----------|------|--------|------|
| **カレンダー**（歯医者・会議） | appointment — その時刻に **始まる** | 直前の「もうすぐやで」だけ | S2 短冊 → **S3** nudge |
| **会話由来 open loop**（申請書・角煮） | task — 期限までに **終わらせる** | 期限過ぎの「片付いた？」 | **S1** OL6 outbound |
| **明示リマインド** | commitment | due で一言 | 既存 reminder |

#### やること / やらないこと

| やる | やらない |
|------|----------|
| `calendar_expectations` の start 前 `pre_window` で outbound | カレンダー予定を Open Loop に自動注入 |
| `urgency` = earliness（例: 15 分前） | 開始後・終了後の「片付いた？」 |
| 台詞は開始 nudge（決定的 · LLM なし） | 終了後の社交一声を concern に混ぜる（「どうやった？」は return-signal 系 · 別判断） |

#### 境界（v0 で割り切り）

- カレンダーに書いた **〆切イベント**（「申請書〆切」）は appointment として扱い、開始 nudge のみ。task 化はしない（実害小）。要るなら後で題名 allowlist / e4b。
- GAPI-3（会話 loop ↔ Calendar 突合）は **別トラック**。S3 の前提ではない。

#### 受け入れ（仮 · 実装時に確定）

| 項目 | 値 |
|------|-----|
| 入力 | S2 `calendar_expectations` の start |
| urgency | `f(earliness)` — start − now ∈ pre_window |
| evidence_gap | v0: 開始の陽性証拠なし ⇒ 1.0（在席・外出検知は後） |
| 発話 | 「まー、もうすぐ {summary} の時間やで」系 · one-shot |
| ゲート | presence · boundary · outbound cooldown · commitment due 優先（S1 と同型） |
| 痕跡 | nudge 成功後に card / event_id を「すでに言った」印 |

うるささリスク最大 → **S1 で θ を校准してから** ship。

### 判断が止まっているときの分解パターン（まー 2026-07-17）

「数値化できないから ship できない」項目は、次の 4 問に分解すると道が見えやすい:

1. **入力信号は何か**（何を notice するか）
2. **内部状態は何か**（gap / concern など、何が立ち上がるか）
3. **閾値はいくつか**（意図と行動のゲート）
4. **行動と痕跡は何か**（act + remember + schedule）

B 軸 concern はこのテンプレの第一例。他チャンネル（A 軸の文学・好奇心、WS-5 の事実ギャップ）も同型で試せる。

---

## 体感ギャップ（運用で見えてる穴）

1. 裏は動くが肌で感じない（UI / 着信 / 会話に薄い）
2. 調べても台詞に載らない（prefetch と表層の切れ目）
3. `agent_observation` / `think_or_discuss` が監査ログ・テンプレに見える
4. 外向き自発が接触一声に偏る（共有・好奇心チャンネルが弱い）
5. 動機側の閾値が未決で ship しにくい → **B 軸 concern 式で第一チャンネル化**（上節）

---

## 実装の進め方（この doc の役割）

- **正本**: 二軸 · 目的別動機 · KJ 的思考 · **B 軸 concern モデル**
- **実装本体**: 既存トラックに分散。**S1** = OL6 outbound · **S2** = calendar expectations（silent）
- **S1/S2 残**: ma-home 運用確認 · θ / lookahead 校准
- **次**: S3 pre_window nudge（カレンダー開始前のみ · 知る→関心→発話）

---

## 参照（会話由来）

- 北極星合意: 「いちばんは生きてる感」（2026-06-25）
- WS-5: 会話の広がり・自発検索（2026-06-30 以降）
- 判断基準の数値化が残件の本丸（2026-07-15）
- 目的別の動機パラメータ（2026-07-16）· [UEC ニュースリリース PDF](https://www.uec.ac.jp/about/publicity/news_release/2021/pdf/20211126_3927.pdf)（感情ダイナミクス参考）
- 二軸 + KJ 的思考（2026-07-17）
- B 軸: S1→S2→S3 · concern モデル · Somatic 対人版（2026-07-17 · まー合意）
- **開始 nudge ≠ 終了確認**: 入口分離（calendar→S3 · open loop→S1）。カレンダーの OL 自動注入はしない（2026-07-17 · まー合意）
