# koyori バックログ — トピック索引

**ダッシュボード**: [backlog-ma-home.md](./backlog-ma-home.md)  
**読み方**: [README.md](./README.md) · [archive-index.md](./archive/archive-index.md)

---

## ma-home トラック

| トピック | 状態 | 読む場所 |
|---------|------|----------|
| **設計方針** | ✅ | [architecture/cognitive-layers.md](./architecture/cognitive-layers.md) |
| **ALIVE / LW** | 🔥 | [tracks/alive-lw-read.md](./tracks/alive-lw-read.md) |
| **GW-SILENT** | ✅ S1 · ✅ S2（opt-in） | [tracks/gw-silent.md](./tracks/gw-silent.md) |
| **OL5** | 🔥 OL5-a 確認 · 📋 close | [tracks/ol5.md](./tracks/ol5.md) |
| **MEM-8** | 概念済 | [architecture/mem-8-encode-retrieve.md](./architecture/mem-8-encode-retrieve.md) |
| **MEM パイプライン** | 運用+未 | [architecture/mem-pipeline.md](./architecture/mem-pipeline.md) |
| **OBS** | 📋 | [tracks/obs.md](./tracks/obs.md) |
| **CAM** | 💤 | [tracks/cam-tapo-ptz.md](./tracks/cam-tapo-ptz.md) |
| **EAR** | 📋 | [tracks/ear.md](./tracks/ear.md) |
| **VIS** | 💤 | [tracks/vis-health.md](./tracks/vis-health.md) |
| **GAPI** | 📋 | [tracks/gapi.md](./tracks/gapi.md) |
| **V / Surface UI 残** | 部分済 | [tracks/surface-vision.md](./tracks/surface-vision.md) |
| **BIO-8** | ✅ | [heartbeat-loop.md](./architecture/heartbeat-loop.md) § Somatic |
| **Outbound** | ✅ | [architecture/outbound-channels.md](./architecture/outbound-channels.md) |
| **プラットフォーム** | ✅ | [architecture/platform-ma-home.md](./architecture/platform-ma-home.md) |

## RP — 人格の基底化

| Phase | 内容 | 状態 |
|-------|------|------|
| 0–1 | SOUL.core + LM Studio system | **済** |
| 2 | persona LoRA + JSONL export | **2a 済** |
| 3 | arc → SOUL（MEM-6） | 未 |

→ [ops/role-persistence-ma-home.md](./ops/role-persistence-ma-home.md) · VIS 間接視覚は [vis-health.md](./tracks/vis-health.md)

## WS — Web

| ID | 読む場所 |
|----|----------|
| WS-1〜2c | [ops/ws-2-conversation-web-search.md](./ops/ws-2-conversation-web-search.md) |
| WS-5 自発検索 | [ops/ws-5-spontaneous-search.md](./ops/ws-5-spontaneous-search.md) |

## 運用スクリプト

→ [ops/scripts-reference.md](./ops/scripts-reference.md)

---

## 本番: Keychron K4 MAX Bluetooth

→ [ops/koyori-input-sharing.md](./ops/koyori-input-sharing.md)

## キオスク URL

既定 **presence-ui `:8090`**（8080 直結ではない）。

```bash
cd ~/src/embodied-claude/scripts/koyori-kiosk
sudo ./install-koyori-kiosk.sh
```

`http://ma-home.local:8090/?kiosk=1`

## Input Leap — 済（V5）

→ [ops/koyori-input-sharing.md](./ops/koyori-input-sharing.md) · [ops/koyori-kiosk-ime.md](./ops/koyori-kiosk-ime.md)

診断: `check-koyori-stack.ps1`（ma-home）

## タッチキーボード（onboard）— 保留

`KOYORI_ONBOARD=1` / `apt install onboard`
