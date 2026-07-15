# V — Surface ビジョン・部屋 UI 残件

**状態**: 部分済（V5 Input Leap ✅）  
**関連**: [koyori-kiosk-browser.md](../ops/koyori-kiosk-browser.md)、[backlog-koyori.md](../backlog-koyori.md)

8080 プロキシ本線・Native chat・キオスク着信・Tapo 視界・るな TTS 等は **実装済み**。以下は残イメージ。

---

## 優先表

| 優先 | ID | 内容 | 状態 |
|------|-----|------|------|
| 中 | V1 | 感情色の部屋（`Emotion` 連動背景） | 未 |
| 低 | V2 | イントロ演出（スプラッシュ・GIF） | 未 |
| 低 | V3 | 発話ビジュアル（るな再生中波形） | 未 |
| 中 | V4 | **see_near** — 近目（方針 B': 在席ゲート主 · 観察は明示時） | Phase 1–3a ✅ · timer 既定OFF · **次=speakゲート near→far** → [koyori-near-eye.md](../ops/koyori-near-eye.md#利用スコープ確定-2026-07-14--b) |
| 高 | V5 | Windows KB をキオスクで共有（Input Leap） | ✅ 2026-06-26 |
| 低 | V6 | 家族・関係サイドバー | 未 |
| 低 | V7 | enriched user 履歴後処理削除（JSONL 純発話後） | 未 |
| 中 | V8 | `room_say` poll フォールバック（SSE 未接続時） | 未 |
| — | V9 | Linux Cage キオスク（Win Surface が本線） | 任意 |

## C トラック残（任意）

| ID | 内容 | 状態 |
|----|------|------|
| C11c | 視界強化（ドロワー大プレビュー） | 未 |
| C11d | 状態圧縮サマリ2枚 | 折りたたみで代替済 |
| — | 体温 LHM | LibreHardwareMonitor、未起動時 ACPI |

## 本番方針（合意 2026-06-10）

- 会話 = Native `/api/native/chat`
- **8080 に新機能を載せない**（webui Task は任意）
- 本番 URL = `:8090`（`:8080` 直結ではない）

V4 see_near は VIS（間接視覚）・EAR と同様 **gateway prefetch** パターンで設計する想定。

全文: [archive § V](../archive/backlog-ma-home-full-2026-06-26.md#v--ビジョン--未実装docsweb_ui_designmdexported-sessionmd-より)
