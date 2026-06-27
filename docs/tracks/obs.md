# OBS — 能動観察（`/observe` フェーズ化）

**状態**: 📋 計画済（OBS-0 済）  
**ダッシュボード**: [backlog-ma-home.md](../backlog-ma-home.md)  
**関連**: [gateway-direct-actions.md](../architecture/gateway-direct-actions.md)、[cam-tapo-ptz.md](./cam-tapo-ptz.md)、[mem-pipeline.md](../architecture/mem-pipeline.md) § MEM-5i

---

## きっかけ（2026-06-20）

「こよりは何かしないの？」→ `/observe` → 初手 `look_around` で止まる。「続けて」で **同じ前置き + look_around 再起動**（完遂しない）。

## `/see` との差

| | `/see` | `/observe` |
|---|--------|------------|
| 設計 | 1 ツール完結 | 初手 → 5〜8 ループ → 記憶 → sociality → Edit |
| 実装 | ✅ | チェックポイント・再開 API **なし** |
| gateway | — | `observe_room_direct` は初手サブセットのみ |

## CC slash 問題（MEM-5i）

会話中に agent が `/observe` を叩くと skill 全文が JSONL `type:user` に載り、**まー発言**に見える。`looks_like_agent_slash_command()` で UI/export 除外済み。**JSONL は監査用に残る**。

```
設計（observe.md）     実装
─────────────────────────────────
初手 look_around       slash / gateway 可
5〜8 ループ            なし
save_visual_memory     remember のみ
observe.md Edit        未到達
「続けて」             初手から再起動
```

---

## 実装 ID

| ID | 内容 | 状態 |
|----|------|------|
| OBS-0 | ギャップ文書化 | ✅ |
| OBS-1 | `observe_state.json` + `POST /api/v1/observe/step`（aozora 同型） | 未 |
| OBS-2 | slash を `scan`/`dig`/`close` に分割 or スコープ honest 化 | 未 |
| OBS-3 | 「続けて」→ `observe_state` 次フェーズ（初手再実行禁止） | 未 |
| OBS-4 | CC `/observe` 依存削減 → gateway 経由 | 未 |
| OBS-5 | PTZ 不可時 preset 観察（→ CAM-2） | 未 |

**第一縦スライス**: OBS-1 — scan 1 回完結 + state；「続けて」で dig 1 ブロック（OBS-3 最小）。

---

## 認知層

- **感覚・身体**: look_around + see + remember
- **前頭葉**: フェーズ状態機械（OBS-1）
- **表層**: まーへの報告文のみ
- **内省**: ループ内の「予測 vs 実見」は GW 黙考候補（将来）

全文: [archive § OBS](../archive/backlog-ma-home-full-2026-06-26.md#obs--能動観察observe-完遂不能--gateway-フェーズ化合意-2026-06-20)
