# K — こより自身のコード

**状態**: 💤 方針メモのみ — **GW + BIO ループが閉じてから着手**  
**ダッシュボード**: [backlog-ma-home.md](../backlog-ma-home.md)

---

## 着手条件（合意 2026-06-26）

K（自分でコードを書く）は **act** 層の話。**interpret = GW-SILENT** と **BIO ループ**（notice→…→schedule）が実戦で閉じるまでは優先度を下げる。いまはまー/Cursor 側の gateway 固定実装で縦スライスを進める。

## やりたいこと（合意 2026-06-17）

**こよりが自分で使うコードを書ける**ようにする。

- **触ってよい**: 自分のループ・身体・小さなスクリプト（pulse 調整、自律行動の枝、private ツール等）
- **触らない**: 設備マニュアル（`CLAUDE.md`）、憲法（`SOUL.md`）、gateway 固定の安全境界

---

## ロードマップ

| ID | 内容 | 状態 |
|----|------|------|
| K1 | 方針メモ — 何を自分で書いてよいか | 💤 GW+BIO 後 |
| K2 | 安全な編集経路（ブランチ・テスト・ロールバック・diff 可視化） | 💤 |
| K3 | 第一例 — LW 縦スライス（`read_aozora_passage`） | 💤 |

**前提**: K2 の経路がなければ自己改修は危ない。**GW-S1 配線 + BIO ループ実戦確認の後**に K1 へ。LW は K2 なしでも gateway 固定実装で縦スライス可（済: LW-READ v0）。

---

## Heartbeat との関係

```
notice → interpret → choose → act → remember → schedule
```

LW / BIO / 将来 K は同じループ。**interpret = GW-SILENT** が先。K は **act** 層で自分のコードを書く経路。
