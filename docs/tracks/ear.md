# EAR — 耳（環境音 / Surface マイク）

**状態**: 📋 計画済  
**関連**: [vis-health.md](./vis-health.md)（見ると同型）、[heartbeat-loop.md](../architecture/heartbeat-loop.md) § BIO-8

---

## きっかけ（2026-06-19）

家の日常会話・TV・部屋の音を拾い **social-state / 判断 / 記憶** へ。「教えてもらう」のではなく **自分で聞く**。

**ハード**: **Surface キオスク内蔵マイク**。Tapo `listen` は遠隔用。家全体常時録音は v0 では想定しない。

## 希望と恐れ

| 力 | こより向け |
|----|------------|
| **希望** | 部屋の連続性・話しかけていい空気・雨/TV の余白 |
| **恐れ（ブレーキ）** | 監視・家族プライバシー・誤反応（ドラマに突っ込む）→ boundary |
| **恐れ（スパーク）** | 気配が分からず割り込みが盲 — **全文ログは不要** |

## 方針

常時・全文・家全体ではなく **気配 → 必要なとき短く聞く → ほとんど捨てる**。

```
Surface mic → VAD / 活動ラベル
           → ingest_social_event（高信頼時のみ transcript）
           → should_interrupt / compose
           → salient 断片だけ save_audio_memory
```

---

## 実装 ID

| ID | 内容 | 状態 |
|----|------|------|
| EAR-0 | ポリシー（TV 連続 transcript 禁止、第三者、電話） | 未 |
| EAR-1 | 活動ラベルのみ（transcript なし） | 未 |
| EAR-2 | bounded キャプチャ + BIO-8 耳 probe | 未 |
| EAR-3 | 高信頼 transcript → open loop / 応答 | 未 |
| EAR-4 | salient clip のみ `save_audio_memory` | 未 |
| EAR-5 | presence-ui キャプチャ API（MCP 経由しない） | 未 |

**第一縦スライス**: EAR-0 + EAR-1 — 活動ラベルだけ social、黙る。

**既存**: wifi-cam `listen`、PC `/voice`（意図的発話のみ）、BIO-8「耳」行（反射未）。

---

## 認知層

- **感覚・身体**: mic capture、Whisper
- **前頭葉**: VAD / 活動分類、保存ポリシー
- **脊髄**: 無音・Whisper 失敗 → BIO-8
- **表層**: まー向け発話は高信頼時のみ

全文: [archive § EAR](../archive/backlog-ma-home-full-2026-06-26.md#ear--耳環境音--surface-マイク合意-2026-06-19)
