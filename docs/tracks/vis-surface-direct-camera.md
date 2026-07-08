# VIS-SD — Tapo see を Surface 12b multimodal へ

**合意**: 2026-07-04（まー）  
**親**: [surface-direct-llm.md](./surface-direct-llm.md) · [surface-vision.md](./surface-vision.md)  
**前提**: チャット画像添付 POC（`prepare_chat_image_data_url` → `build_surface_image_turn_messages`）が ma-home で動作済み

---

## 問題

| 経路 | 今 | 限界 |
|------|-----|------|
| see intent + native chat | Tapo JPEG → **e4b** `describe_image_outcome` → `[vision_prefetch]` テキスト → **12b-qat** テキストのみ | 見るモデルと話すモデルが分離。「こよりが見た」感が弱い |
| チャット添付 | JPEG → **12b-qat** multimodal 直 | ✅ 同一モデルで見て答える |

**欲しいもの**: 「見て」「部屋どう？」等の see intent でも、添付画像と同じ **12b multimodal ターン**で Tapo キャプチャを渡す。

---

## 経路整理（2026-07-06）

| 経路 | こよりへ渡すもの | ワンクッション |
|------|------------------|----------------|
| **native chat「見て」**（Surface Direct） | JPEG → 12b multimodal 直 | なし ✅ |
| **legacy `/api/chat`「見て」**（Surface Direct） | 同上（`stream_surface_reply_ndjson`） | なし ✅ |
| **legacy CC**（`PRESENCE_SURFACE_USE_CLAUDE=1`） | `[vision_prefetch]` キャプション文字列 | あり（非本線） |
| **自律 tick `observe_room`** | look_around のみ（**OBS-TICK-0** · caption/remember 停止） | [obs-tick-encode.md](./obs-tick-encode.md) |

**廃止したい旧フロー（会話）:** 画像 → neutral caption LLM → キャプションを gateway に注入 → こよりがテキストだけ読む。

---

### Before

```
まー「部屋見て」
  → capture_for_mode (Tapo)
  → e4b VISION_CAPTION
  → intercept に [vision_prefetch] テキスト注入
  → generate_surface_reply（テキストのみ）
```

### After（本線・Surface Direct）

```
まー「部屋見て」
  → capture_for_mode（e4b スキップ）
  → prepare_chat_image_data_url
  → intercept（vision_prefetch テキストなし）
  → build_surface_image_turn_messages（image_source=camera）
  → 12b-qat が JPEG + 発話で返答
```

### e4b-qat は残す用途（classifier のみ）

- OL-GATE / Stage1/2 / GAPI-2b 等 — `PRESENCE_CLASSIFIER_MODEL`

### 12b-qat vision describe（tick / MCP / legacy prefetch）

- `wifi_cam_mcp.vision.describe_image_outcome` → **12b-qat**（`resolve_vision_lm_model`）
- `PRESENCE_CAMERA_VISION_VIA_SURFACE=0` ロールバック時も caption は 12b（テキスト prefetch）

---

## フラグ

| 変数 | 既定 | 意味 |
|------|------|------|
| `PRESENCE_CAMERA_VISION_VIA_SURFACE` | （廃止）Surface Direct なら常に 12b multimodal 直渡し |
| `PRESENCE_SURFACE_DIRECT` | `1` | 表層直 LM（無効時は従来 e4b prefetch） |
| `PRESENCE_GATEWAY_VISION_PREFETCH` | `1` | see intent 自体の有無（0 なら capture もしない） |

`PRESENCE_CAMERA_VISION_VIA_SURFACE` は廃止（Surface Direct = 常に直渡し）。legacy CC のみ `[vision_prefetch]` テキスト経路が残る。

---

## 実装フェーズ

| # | 内容 | 状態 |
|---|------|------|
| **1** | `capture_for_surface_multimodal` — capture のみ、data URL 返却 | ✅ 2026-07-04 |
| **2** | `see_prefetch` — surface 時 `image_data_url`、vision_note 省略 | ✅ 2026-07-04 |
| **3** | `native_chat_router` — camera image を `_stream_surface_chat` へ | ✅ 2026-07-04 |
| **4** | `chat_image` / `llm` — camera 用 enriched + system 文言 | ✅ 2026-07-04 |
| **5** | pytest（prefetch mock・messages 断言） | ✅ 2026-07-04 |

---

## 検証（LM Studio ログ）

**Broken（旧）**: 12b 入力がテキストのみ + `[vision_prefetch]`；別リクエストで e4b に `<|image|>`

**OK（新）**: 12b user turn に `<|image|>` + 短い発話；同一ターンに `[vision_prefetch]` なし

```powershell
.\scripts\restart-presence-ui.ps1
# キオスクで「部屋見て」→ LM Studio で 12b に image トークン
```

---

## 残件（本 track 外）

- V4 **see_near**（Surface 内蔵カメラ）
- 返答後の caption を memory に非同期保存
- `chat_stream.py` legacy 8080 経路の surface multimodal（native のみ本線）
