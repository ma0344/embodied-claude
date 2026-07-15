# Kiosk primary + room_say — 動作確認

Surface が「こよりの本線」のとき、PC スピーカーは黙り、キオスクからるなの声が出る。

## 前提

1. `http://<ma-home-ip>:8090/?kiosk=1` を **Surface で開く**（`?kiosk=1` 必須）
2. 画面を **1回タップ**（ブラウザの自動再生ロック解除）→ ハンバーガーメニュー → **音量** + **音声テスト**
3. **無音のとき** — メニュー内スライダー（部屋の再生）と **設定 → サウンド**（Windows 全体）の両方を確認
4. **AivisSpeech が ma-home PC で起動** — `scripts/start-aivis-tts.ps1`（`:10101`）。未起動だとキオスクは `surface TTS 502/503`
5. `restart-presence-ui.ps1` 済み（8090 のみ使うなら Claude Code 再起動は不要）
6. 診断: `curl -s http://127.0.0.1:8090/api/v1/ui-config` → `"kiosk_primary_active": true` **かつ** `"surface_tts_ready": true`

`kiosk_primary_active` が `false` のときはキオスクがサーバーに未登録（SSE 未接続 or 古い app.js で `client_id` が `web-*` のまま）。

## 会話で say を試す

| 場所 | やり方 |
|------|--------|
| **Claude Code（PC）** | `/talk` スキル or 通常会話で plan が `say` 許可時 → MCP `say` |
| **8090 部屋（PC/キオスク）** | チャット送信。モデルが `say` ツールを呼べば同じ経路 |
| **自律 tick** | `miss_companion` 等 → outbound 着信（`room_inbound`）+ キオスク TTS |

`/talk` は **Claude Code のスラッシュコマンド**（ブラウザの URL ではない）。

## 手動スモーク（room_say のみ）

```powershell
# キオスクを ?kiosk=1 で開いた状態で true であること
curl -s http://127.0.0.1:8090/api/v1/ui-config

curl -X POST http://127.0.0.1:8090/api/v1/tts/room-say `
  -H "Content-Type: application/json" `
  -d '{"text":"まー、キオスクから聞こえる？"}'
```

キオスクから声が出れば SSE + surface TTS は OK。出なければタップ解除 or Aivis `:10101` を確認。

## よくある原因

- Surface URL に `?kiosk=1` がない → `client_id` が kiosk にならない
- 古い `app.js` キャッシュ → Ctrl+Shift+R
- `kiosk_primary_active: false` → キオスク側で SSE 切断、90s 待つかタブを前面に
- **画面タップ前は無音** — ブラウザの自動再生ポリシー（OS 音量とは別）。タップ後に急に聞こえ始めるのはこれ
- Surface **システム音量が 0** → API は `routed to kiosk` でも無音
- **物理音量ボタンで OSD が出ない** — Edge 全画面などでは出ないことがある。設定 → サウンド、または音量ミキサーで **Microsoft Edge** のスライダーを確認
- **二重再生（エコー）** — `kiosk_say` 経路は `room_say` のみで TTS。outbound `speak` と同時だと同一文が2回鳴る（`enqueue` は `speak=False` + `kiosk_say=True` で整合）
