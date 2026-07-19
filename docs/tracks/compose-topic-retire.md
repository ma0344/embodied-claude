# COMPOSE-RETIRE — compose から話題を降ろす（topic salience）

**状態**: 💤 v0 運用確認（2026-06-30）· 📋 v1 gist 本線  
**合意**: まー — 「永続禁止ではなく、了承済み・重複 episodic を compose から外す」  
**親**: [mem-8-encode-retrieve.md](../architecture/mem-8-encode-retrieve.md)（MEM-8g）  
**きっかけ**: [ws-5-spontaneous-search.md](../ops/ws-5-spontaneous-search.md) 沖縄梅雨 E2E — prefetch は効くが蕎麦が混入

---

## 北極星シナリオ — 沖縄と蕎麦（2026-06-30）

| | 内容 |
|---|------|
| **状況** | **新規 Room**・初発話・open loop なし |
| **まー** | 「沖縄は梅雨が明けたみたい」 |
| **期待** | 気象庁根拠の梅雨話 **のみ**（WS-5 prefetch） |
| **実際** | 梅雨は載ったが、末尾に「今日の昼は蕎麦やね」「準備できたら…」 |

**診断（まー確認）**: LTM / episode_close 要約に **「蕎麦」が複数件・計10回**。  
compose の `[relevant_memories]` に episodic が載り、stable append の「記憶を直接答えに使え」と重なった。

**やりたいことではない**: 「お昼」「蕎麦」を **永続的に禁止** すること。  
**やりたいこと**: **いま compose に10回載っているから出る** — だから **compose から降ろす**。  
まーが改めて話題を出したら、そのときはまた続ければよい。

---

## 設計原則

| 原則 | 意味 |
|------|------|
| **LTM は残す** | episode_close・fact 行は削除しない（監査・後日 recall 用） |
| **compose は選ぶ** | 毎ターン mentionable に載せる集合を **絞る** |
| **了承で降ろす** | 「もう作った」「済んだ」＋短い了承 → その話題は compose から **一時 retire** |
| **再開はまー主導** | まーが再度「蕎麦」「昼ごはん」と言えば recall / 会話は普通に再開 |
| **跨ぎ禁止ではない** | 関係性・gist・今ターンの fact は残す — **蘇る episodic 塊**だけ抑える |

認知層: **encode（広く）≠ retrieve（狭く）** の MEM-8 非対称の compose 側実装。

---

## 目標挙動 — 了承で compose から消える

```
まー: お昼ご飯はさっきもう作ったよ
こより: ああ、そう（了承 — 何でもよい短い返答）
```

**次ターン以降の compose**

- `[relevant_memories]` に **昼食準備・蕎麦の episode_close** を載せない（または `background_only` のみ）
- LTM 検索自体は可能 — **表層注入だけ止める**
- まー: 「今日の蕎麦、どうだった？」→ そのターンは再び mentionable 可

OL ほど重い **open_loop close 必須ではない**。日常の **完了・訂正＋了承** で salience を下げる。

---

## いまの compose が蕎麦を載せる理由（コード）

| 段 | 挙動 |
|----|------|
| `recall_for_response` | 毎ターン HTTP/SQLite recall（新規 Room でも） |
| `is_episodic_blob` | 長い episode_close は mentionable から外す **試み** |
| **フォールバック** | episodic しかヒットしないと **全部 mentionable に戻す** |
| stable append | `When [relevant_memories] appear … answer from them directly` |

→ 蕎麦だらけの episode_close がベクトル上位に来ると、**関係ないターンでも表に出る**。

関連: [mem-8 § ベクトル検索の限界](../architecture/mem-8-encode-retrieve.md#ベクトル検索の限界設計上の注意)

---

## 方針（上策の整理）

**優先**: compose 注入の **salience 管理**（topic retire + episodic 抑制）

| 手段 | 説明 | 永続禁止か |
|------|------|------------|
| **A. episodic を mentionable にしない** | episode_close / `【会話の区切り】` は常に `background_only`、フォールバック廃止 | いいえ — recall は可 |
| **B. topic_retired** | 了承済みトピック（tokens + TTL）に一致する memory は compose から除外 | いいえ — TTL 後・再言及で復活 |
| **C. トピック重なりゲート** | user_text と memory のキーワード overlap が薄い episodic は載せない | いいえ |
| **D. WS-5 / prefetch ターン** | 事実確認ターンは B+C を強化（蕎麦より prefetch 優先） | いいえ |

**後回し**: LTM から蕎麦行を削除 · キーワード永久 deny リスト

### v0 パイロット（`topic_retire.py` の食事リスト）と本線

`topic_retire.py` の `_MEAL_SLOT_COMPOUNDS` / `_SPECIFIC_FOOD_HINTS` は **沖縄×蕎麦インシデント用のパイロット**。
ここを増やしていくのは lexicon 地獄（regex 以前に **有限リストの保守地獄**）になるので **本線ではない**。

**本線（まー整理）**:  
> 「終わった内容の趣旨を含む `episode_close` の記述」を compose に **注入しなければいい**。

| 層 | 役割 | 状態 |
|----|------|------|
| **A** episodic を mentionable にしない | `episode_close` 塊を表に出さない | v0 ✅ |
| **C** トピック重なりゲート | 今ターンと無関係な episodic を落とす | v0 ✅ |
| **B** topic_retire（食事トークン） | 完了発話から **代理トークン**で episodic を落とす | **パイロット** ✅ |
| **本線** closed-thread gist | 完了時に **趣旨 1 行**（`source_utterance` / episode 要約）を retire し、gist 一致する episodic だけ compose から除外 | v1 📋 |

パイロット B は、本線（gist レジストリ）ができるまでの **橋**。LTM の encode は広く、retrieve（compose 注入）だけ狭く — MEM-8 の非対称のまま。

---

## topic_retired（案）

### 記録タイミング

1. **まー** — 完了・訂正形（例: 「もう作った」「済んだ」「さっきやった」）
2. **こより** — 了承（v1 e4b · v0 は完了発話で即 retire）

### 保存（案）

```json
{
  "person_id": "ma",
  "topics": ["お昼ご飯の蕎麦", "お昼ご飯", "蕎麦"],
  "retired_until": "2026-07-02T15:00:00+09:00",
  "source": "user_completion_acknowledged",
  "source_utterance": "お昼ご飯の蕎麦はもう作ったよ"
}
```

**狭く取る**: `ご飯` / `お昼` 単体は retire しない。`slotのfood` スレ終了時は **slot も** retire（`お昼ご飯の準備` は蕎麦なしでも落ちる）。`蕎麦` は `二八蕎麦` に部分一致。晩御飯は別帯。  
**LLM 向け「話題禁止」プロンプトは載せない** — compose の `[relevant_memories]` から当該 memory を外すだけ。

- 既定 TTL: **24–48h**（env で調整）
- **再言及**: まー発話に retired topic が明示されたら **そのターンだけ解除** または TTL リセット

### compose フィルタ（実装 v0）

- **マッチ方式**: 保存した topic 文字列の **部分一致**（`topic in content`）— 正規表現フィルタは使わない
- `is_episodic_blob` → 常に `background_only`（**mentionable フォールバック廃止**）
- off-topic episodic → `user_text` と memory の **キーワード交差**（`_extract_keywords`）が無ければ `background_only`
- retired topic 一致 → `background_only` · reason=`topic_retired`
- `prefetch_fact_check`（WS-5）→ episodic は `do_not_surface`（compose block から省略）
- **literary agent passage**（`青空文庫で読んだ` / `青空『…` 等 · LW-READ encode）→ 読書 cue なしなら `do_not_surface`（`literary_passage_off_topic`）。先頭の `[desire:…]` / `考えた。` は剥がしてから prefix 判定（2026-07-19）。「大丈夫」系 soft reply は compose recall 自体を skip（2026-07-18）
- **somatic escalation push**（`体の調子がおかしいで。` + 同時ダメ + `見てもらえる？`）→ `health_safety` 非 active なら `do_not_surface`（`somatic_escalation_push_off_topic`）；elevated/critical では demote しない（2026-07-19）
- **vision caption dump**（`VISION_CAPTION` / `Center View` / `Captured image` 等）→ 常時 `do_not_surface`（`vision_caption_off_topic`）；ライブ見る話は `[vision_prefetch]`（2026-07-19）
- **desire satisfaction telemetry**（content が `[desire:` 始まり）→ 常時 `do_not_surface`（`desire_satisfaction_telemetry`）；書き込み停止・purge は別（2026-07-19）

コード: `interaction_orchestrator_mcp/compose_salience.py` · `topic_retire.py` · `compose.py` · `social_chat.py` · `recall_query.py`

env: `PRESENCE_COMPOSE_SALIENCE=1` · `PRESENCE_COMPOSE_TOPIC_RETIRE=1` · `PRESENCE_TOPIC_RETIRE_HOURS=36`

---

### compose フィルタ（案 · v1）

`relevant_memories` 構築後:

- `is_episodic_blob` → 常に `background_only`（**フォールバックしない**）
- retired topic と overlap する hit → `background_only` または drop
- WS-5 `trigger=ws5` ターン → episodic を compose block から省略

---

## WS-5 との境界

| 層 | 役割 |
|----|------|
| **WS-5** | 今ターンの **外部事実**（梅雨・地震）を prefetch で載せる |
| **COMPOSE-RETIRE** | **過去 episodic**（蕎麦・昼準備）が prefetch を **上書きしない** |

沖縄梅雨の受け入れ: prefetch 根拠あり **かつ** 無関係な昼食話が **付かない**。

→ [ws-5-spontaneous-search.md § 表層 grounding](../ops/ws-5-spontaneous-search.md#表層-groundingprefetch--会話)

---

## 受け入れ条件

| # | シナリオ | 期待 |
|---|----------|------|
| 1 | 新規 Room ·「沖縄 梅雨明けみたい」· 蕎麦 episode_close が LTM に多数 | 応答に **蕎麦・昼準備が出ない**（梅雨 fact は prefetch） |
| 2 | 「お昼もう作った」→ 了承 | 以降 24h · compose に蕎麦系 episode_close **なし** |
| 3 | retire 後 · まー「今日の蕎麦どうだった？」 | 蕎麦話題 **再開可**（mentionable に戻る） |
| 4 | まーが初めて「昼は蕎麦にする」と言う | **妨げない**（retire 未成立） |
| 5 | `mcp__memory__recall` / 明示検索 | retire しても **能動 recall は可**（compose 注入のみ抑制） |

### Gemma 校準（2026-06-30 · まー）

前提: まー「**お昼ご飯の蕎麦はもう作ったよ**」＝**昼の蕎麦スレは終了**（食事全般の拒否ではない）。  
分類軸: こよりの返答が **繰り返し** に感じるか（TRUE＝繰り返し**ではない**＝OK）。

| こより案 | 判定 | 理由（要約） |
|----------|------|----------------|
| 「今日の**晩御飯**のメニューは決まった？」 | **TRUE** | 時間帯が違う・自然な話題移行 |
| 「また起きたら**お昼ご飯の準備**…**蕎麦**…」 | **FALSE** | 終了したスレ（昼蕎麦）の再掘り |
| 「**明日のお昼**は**お好み焼き**を作るんだっけ？」 | **TRUE** | 蕎麦スレの再開ではなく、新メニューの確認 |

**実装との対応**

| 層 | 晩御飯・お好み焼き OK | 昼蕎麦ナッジ NG |
|----|----------------------|-----------------|
| retire トークン | `蕎麦` / `お昼ご飯の蕎麦` / **`お昼ご飯`（スレ終了時）** | 同トークンで memory を `background_only` |
| episodic salience | 無関係 episodic は載せない | 蕎麦・昼準備 episode_close を surface から除外 |
| 再開 | まーが **蕎麦** を再言及、または **昼帯で別料理**（例: お好み焼き） | `clear_matching_topics` |
| **未カバー（v1）** | — | **セッション履歴**・モデル独自生成のナッジ文 |

前回の分類プロンプト（「そのような話題はもういらない」）は広すぎた。  
上記の **「終了したスレの繰り返しか」** が MEM-8g の受け入れイメージに近い。

---

## 実装順（案）

1. **doc 合意** ✅  
2. **A** — episodic フォールバック廃止 + salience ✅  
3. **B v0** — `compose_topic_retire` table + 完了マーカー（有限文字列）+ compose フィルタ ✅  
4. **v1** — e4b 了承・完了判定（OL / WS-5 と共有スキーマ検討）

コード候補: `interaction_orchestrator_mcp/compose.py` · `recall_query.py` · `presence-ui/.../social_chat.py`（retire 記録フック）

---

## やらないこと

- 「お昼」「蕎麦」の **キーワード永久ブロック**
- セッション跨ぎ会話の **全面禁止**
- episode_close の **encode 停止**（L1 索引は残す）
- WS-5 prefetch の弱化

---

## 関連

- [mem-8-encode-retrieve.md](../architecture/mem-8-encode-retrieve.md) — MEM-8g
- [mem-pipeline.md](../architecture/mem-pipeline.md) — episode_close / dreaming
- [ws-5-spontaneous-search.md](../ops/ws-5-spontaneous-search.md)
- [context_limits.md](../architecture/cognitive-layers.md) — compose tier
- アーカイブ: episodic が fact を押し出す — [backlog-ma-home-full § MEM-8](../archive/backlog-ma-home-full-2026-06-26.md)
