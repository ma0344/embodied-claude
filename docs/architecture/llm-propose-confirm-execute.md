# LLM 判断 — Propose → Confirm → Execute

**合意**: 2026-06-30（まー）  
**方針**: gateway で LLM（主に e4b 分類器）に **不可逆な副作用**を一発任せない。**確認ステップを挟む**のを当たり前にする。

**関連**: [gateway-direct-actions.md](./gateway-direct-actions.md) · [ol5.md § OL7](../tracks/ol5.md) · [gapi.md § GAPI-7b](../tracks/gapi.md) · [utterance-anchoring.md § TEMP-C5](../tracks/utterance-anchoring.md)

---

## 原則

| 段階 | 誰が | 副作用 |
|------|------|--------|
| **Propose** | e4b / 分類器（stateless） | なし — JSON 候補だけ |
| **Confirm** | 表層こより + まー（会話）または明示 OK | なし — `pending_*` を立てる |
| **Execute** | **gateway のみ**（Python · transaction） | あり — DB / GAPI / close |

> LLM の「一発判断」は **Propose まで**。Execute は gateway が **ブロック結果**（`[calendar_write_result]` · `status=closed`）を見てから。

**心許ないもの**: 分類器の confidence だけでカレンダー insert · loop close · 記憶の上書きを確定すること。

**心許せる例外**（確認スキップ可 · 要ポリシー）:

- **決定的ルール**が先に通ったとき（OL5-b substring · GAPI 正規化後の OK）
- **同一発話に object + 完了語**が明示（「昼寝終わった」）
- 失敗しても **害が小さい**読み取り専用（prefetch · 分類ラベルだけ）

---

## 共有パターン

```
ingest / classify (e4b)
  → gateway: 即 execute | pending | no-op
  → pending なら compose/plan で自然確認
  → record → pending.asked_at
  → 次 ingest: 短答 or 正規化 affirm
  → gateway execute
  → 注入ブロックで表層を正直化
```

**共有プリミティブ**: `open_loops.detail_json.pending_check`（OL6 · OL7 同型 · `trigger` で区別）

---

## 既存の当てはまり

| 機能 | Propose | Confirm | Execute |
|------|---------|---------|---------|
| **GAPI-7b** | Stage2 抽出 · pending draft | こより「入れていい？」· まー OK | `events.insert` · `[calendar_write_result]` |
| **GAPI-7d**（案） | e4b 極性のみ | 7b の会話確認は同じ | gateway |
| **OL6** | compose `loops_due_for_check` | 「掃除、終わった？」→「終わったよ」 | `ol6_completion` |
| **OL7** | e4b 日本語検定型 · 候補 loop | 「散歩行ってきたん？」→「うん」 | `ol7_completion` |
| **OL5-b** | —（regex/union） | — | 即 `ol5_completion`（明示完了） |
| **TEMP-C5**（案） | e4b · `when`→`datetime` | 低 confidence なら「2時からやな？」 | `detail.start_at` 保存 |

---

## 新機能チェックリスト

LLM で「これやる」と判断する経路を足すとき:

1. **副作用は gateway だけか**（LLM に API/DB を渡していないか）
2. **一発で Execute していないか** — 迷ったら pending
3. **確認後の短答ルール**があるか（OL6 `is_pending_completion_confirm` 同型）
4. **表層に success 注入ブロック**があるか（口先完了防止）
5. **pending の `trigger`** を付けてデバッグできるか

---

## コストとのバランス

e4b は **Propose 専用**に寄せ、呼ぶ条件を絞る（open loop あり · pending あり · 正規化 miss 等）。

確認ターンは **会話コスト**だが、誤 close / 誤カレンダー書込より安い。まーとの関係としても自然なことが多い（「行ってきたん？」）。

---

## 実装メモ

- 分類器プロンプトは **会話劇ではなく JSON**（OL7 · GAPI-7d · TEMP-C5）
- `confidence` は **即 execute vs pending** の材料 · 閾値未満＝永久拒否ではない
- 表層 12B と e4b の **役割分離**（PFC-1）を維持
