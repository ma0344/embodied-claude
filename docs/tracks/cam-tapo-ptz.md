# CAM — Tapo PTZ / ONVIF 細かい操作

**状態**: 💤 調査・preset 運用検討  
**関連**: [obs.md](./obs.md) OBS-5、[gateway-direct-actions.md](../architecture/gateway-direct-actions.md)、`wifi-cam-mcp/scripts/test_ptz_probe.py`

---

## きっかけ（2026-06-20）

Tapo の pan/tilt が **細かく効かない**。Synology Surveillance Station 経由でも検証。

## クライアント比較

| クライアント | PTZ |
|--------------|-----|
| DS Cam / SS Desktop | **細かく動く** |
| SS Web Edge | OK |
| SS Web Chrome | **NG**（ブラウザ相性） |
| wifi-cam-mcp 直 ONVIF | JPEG 変化あり、**GetStatus 更新されないことあり** |

**TP-Link FAQ [4465](https://www.tp-link.com/jp/support/faq/4465/)**: Profile S、Camera Account 必須、**同時接続 2 まで**（Care/SD/NAS/DS Cam + ma-home で RTSP 406 ありうる）。

## ma-home 直 ONVIF プローブ（C200）

- RelativeMove: 成功・GetStatus 不変・JPEG hash 変化 → **首は動いた**
- continuous: GetStatus 追従あり
- stream1: 406 → subtype フォールバック

## API から細かく動かせない — 4 原因

| # | 原因 | 対策候補 |
|---|------|----------|
| A | 大ステップ only | degrees 5〜10、preset |
| B | RelativeMove + GetStatus stale | continuous 既定、preset + 内容 recall |
| C | Continuous チューニング | `TAPO_PTZ_MODE=continuous` |
| D | SS ドライバ vs ONVIF 直 | pytapo スパイク（CAM-4） |

`look_around` は `pan_left(45)` 等の **連続 relative** に依存。`camera_go_to_preset` は別経路。

---

## 実装 ID

| ID | 内容 | 状態 |
|----|------|------|
| CAM-1 | `test_ptz_probe.py` 実機切り分け | 一部済 |
| CAM-1b | ONVIF Device Manager 4 軸比較メモ | 未 |
| CAM-2 | **preset-only observe** — relative 依存やめる | 未 |
| CAM-3 | FAQ 4465 + Chrome/Edge 注意を README/CLAUDE へ | 未 |
| CAM-4 | pytapo vs ONVIF 直 | 未 |

Imou は `ptz_mode=continuous` 必須 → [CLAUDE.md](../../CLAUDE.md) カメラ節。

全文: [archive § CAM](../archive/backlog-ma-home-full-2026-06-26.md#cam--tapo-ptz--onvif-細かい操作が効かない合意-2026-06-20)
