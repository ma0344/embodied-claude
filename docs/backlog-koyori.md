# koyori バックログ — トピック索引

**ダッシュボード**: [backlog-ma-home.md](./backlog-ma-home.md)  
**読み方**: [README.md](./README.md)

---

## ma-home トラック（詳細）

| トピック | 状態 | 読む場所 |
|---------|------|----------|
| **ALIVE / LW** 青空読書 | 🔥 v0 運用中 | [tracks/alive-lw-read.md](./tracks/alive-lw-read.md) |
| **GW-SILENT** 黙考 | 📋 S1 未配線 | [tracks/gw-silent.md](./tracks/gw-silent.md) |
| **OL5** 予定消化 | 📋 | [tracks/ol5.md](./tracks/ol5.md) |
| **OBS** `/observe` | 📋 | [archive/backlog-ma-home-full-2026-06-26.md](./archive/backlog-ma-home-full-2026-06-26.md) § OBS |
| **CAM** Tapo PTZ | 💤 | 同上 § CAM |
| **EAR** 環境音 | 📋 | 同上 § EAR |
| **MEM** 記憶層 | ✅ 運用 | 同上 § MEM |
| **GAPI** Calendar/Drive | 📋 | 同上 § GAPI |
| **BIO-8** 神経系 | ✅ | 同上 § BIO-8 |
| **VIS** VL 安定性 | 💤 | 同上 § VIS |

## RP — 人格の基底化

| Phase | 内容 | 状態 |
|-------|------|------|
| 0 | `presets/koyori-SOUL.core.md` → stable append | **済** |
| 1 | LM Studio 固定 system | **済** |
| 2 | persona LoRA + JSONL export | **2a 済** |
| 3 | arc → SOUL パッチ（MEM-6） | 未 |

手順 → [ops/role-persistence-ma-home.md](./ops/role-persistence-ma-home.md)

## WS — 会話中 WebSearch

仕様 → [ops/ws-2-conversation-web-search.md](./ops/ws-2-conversation-web-search.md)（WS-1〜2c **済**）

---

## 本番: Keychron K4 MAX Bluetooth

手順: [ops/koyori-input-sharing.md](./ops/koyori-input-sharing.md)  
`koyori-pair-keychron.sh` / `koyori-connect-keychron.sh`

## キオスク URL（フェーズ3）

既定は **presence-ui `:8090`**（8080 直結ではない）。

```bash
cd ~/src/embodied-claude/scripts/koyori-kiosk
sudo ./install-koyori-kiosk.sh
```

`/etc/default/koyori-kiosk` の `KOYORI_WEBUI_URL`:

`http://ma-home.local:8090/`（`/projects/...` は 8080 用）

キオスク起動時は `?kiosk=1` 自動付与。手動: `http://ma-home.local:8090/?kiosk=1`

## ハードウェア音量キー（C11f+）

| 層 | 内容 |
|----|------|
| acpid | `button/volumeup|down` → `/etc/acpi/surface-volume.sh` |
| 音響 | `wpctl` / `pactl`（PipeWire） |
| オーバーレイ | `koyori-audio-server` `:18791` |

```bash
curl -sS http://127.0.0.1:18791/health
sudo acpi_listen
```

## Input Leap — 済（V5, 2026-06-17）

| 側 | 起動 |
|----|------|
| **ma-home** | `input-leaps.exe -c default.sgc --disable-client-cert-checking --disable-crypto` |
| **koyori** | `KOYORI_INPUT_LEAP_SERVER` + watch |

手順・トラブル: [ops/koyori-input-sharing.md](./ops/koyori-input-sharing.md)  
日本語 IME: [ops/koyori-kiosk-ime.md](./ops/koyori-kiosk-ime.md)

診断: `koyori-diagnose-input-leap` / ma-home: `scripts/check-koyori-stack.ps1`

## タッチキーボード（onboard）— 保留

```bash
KOYORI_ONBOARD=1
KOYORI_OSK_BACKEND=onboard
sudo apt install -y onboard at-spi2-core
```
