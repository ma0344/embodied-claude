# Outbound — 能動届けチャネル

**状態**: ✅ 本線運用中（`kiosk_banner` / `A4h` 未）  
**関連**: [gateway-direct-actions.md](./gateway-direct-actions.md)、[scripts-reference.md](../ops/scripts-reference.md)

---

## 問題

experience だけ増えても **まーが見ている端末に届く保証がない**。`talk_to_companion` は ma-home PC スピーカーのみだった → A4 で部屋着信 + push。

**方針**: 実行後に **OutboundChannel** を明示。`channel` + `delivered` を experience に残す。quiet hours / nudge クールダウンはチャネル単位。

---

## チャネル一覧

| チャネル | 出力先 | 状態 |
|----------|--------|------|
| `room_inbound` | キオスク中央ダイアログ（SSE） | ✅ A4i |
| `chat_compose` | 着信「返事する」→ 新規 native 会話 | ✅ A4j |
| `voice_local` | ma-home PC スピーカー（Aivis） | ✅ |
| `voice_surface` | Surface スピーカー（TTS URL） | ✅ A4c+ |
| `voice_camera` | Tapo / go2rtc | 設定時 |
| `kiosk_banner` | ヘッダー／トースト（視覚のみ） | **未** |
| `push_windows` / `push_android` | ntfy / Pushover | ✅ A4g（env 要） |
| `silent` | private reflection のみ | ✅ |

## 配信モデル（合意 2026-06-16）

- nudge は **会話セッションに属さない**（`session_id` 未知でも届く）
- **Surface** = 8090 中央ダイアログ + TTS
- **PC** = 部屋 UI では届けない → **ntfy/Pushover**（8090 を開いてなくても）
- 着信から新規会話は **キオスク側のみ**
- enqueue 時 **fan-out**（kiosk + push）。PC per-client poll は廃止方向

## 段階

| 段 | 見た目 | 音声 |
|----|--------|------|
| MVP | bubble + poll | Web Speech |
| A4i 本線 | 中央ダイアログ | Web Speech → TTS URL |
| 目標 | SSE `room_inbound` | Server TTS |

## 未着手

| ID | 内容 |
|----|------|
| A4d | チャネル選択（MVP 後の fan-out 整理） |
| A4h | Android Push（ntfy 共用で可） |
| `kiosk_banner` | 視覚のみトースト |

## A4j 着信 UX（修正済み 2026-06-18）

**あるべき流れ**: 「返事する」→ 新規セッション → **こより着信文だけ** bubble → まーが自分の言葉で返信。compose には着信を **gateway メタ** で渡し、ユーザー可視プロンプトにしない。

---

## Push 候補（検討済み）

ntfy、Pushover、Gotify、Telegram Bot、Discord webhook、FCM 専用プロジェクト。

選定: ma-home から HTTP / 受信を ma 専用に閉じる / quiet hours で mute。

全文: [archive § A4](../archive/backlog-ma-home-full-2026-06-26.md#a4--こよりからの能動届けoutbound)
