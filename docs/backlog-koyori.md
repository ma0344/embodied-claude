# koyori バックログ

ma-home 側の全体優先順・記憶 E2E: [backlog-ma-home.md](./backlog-ma-home.md)（2026-06-18 更新）。

## MEM — 記憶層・Dreaming（BIO-8 の次）

4 層（WM≈セッション → STM≈日次 → LTM → Deep/SOUL）と昇格パイプライン。詳細 → [backlog-ma-home.md#mem--記憶層セッション跨ぎ--dreaming](./backlog-ma-home.md)。

## BIO-8 — 神経系（体調の自覚）

ma-home バックログ **BIO-8a〜d** と同じ。こより端では **目・声の不調がキオスクに届く**のがゴール（ステータス／着信／一声）。詳細 → [backlog-ma-home.md#bio-8--somatic-loop神経系体調の自覚](./backlog-ma-home.md)。

## 本番: Keychron K4 MAX Bluetooth

手順: `docs/koyori-input-sharing.md`（MAC はランダムでも名前でペア）  
`koyori-pair-keychron.sh` / `koyori-connect-keychron.sh`

## キオスク URL（フェーズ3）

既定は **presence-ui `:8090`**（8080 直結ではない）。

```bash
# repo 更新後、koyori 実機で再インストール
cd ~/src/embodied-claude/scripts/koyori-kiosk
sudo ./install-koyori-kiosk.sh
```

`/etc/default/koyori-kiosk` の `KOYORI_WEBUI_URL` を手で直す場合:

`http://ma-home.local:8090/`（`/projects/...` は 8080 用。8090 だと JSON 404 画面になる）

キオスク起動時は `koyori-kiosk.sh` が自動で **`?kiosk=1`** を付与（C11b: 全幅チャット + ドロワー）。`kiosk=0` が設定されていても **強制で 1 に差し替え**。手動確認: `http://ma-home.local:8090/?kiosk=1`

repo 更新後は `sudo ./install-koyori-kiosk.sh` で `/usr/local/bin/koyori-kiosk` を再配置してから reboot。

## Input Leap — 済（V5, 2026-06-17）

ma-home KB/マウス → koyori キオスク。**動作確認済み。**

| 側 | 起動 |
|----|------|
| **ma-home** | `Get-Process input-leaps -EA 0 \| Stop-Process -Force` のあと `input-leaps.exe -c default.sgc --disable-client-cert-checking --disable-crypto` |
| **koyori** | `/etc/default/koyori-kiosk`: `KOYORI_INPUT_LEAP_SERVER`, `KOYORI_INPUT_LEAP_CRYPTO=0` → キオスク起動 + **watch**（client 落ちたら再起動） |

Surface だけ再起動した直後は ma-home Server がまだなら client が待つ/リトライ。`koyori-diagnose-input-leap` で確認。

手順・トラブル: `docs/koyori-input-sharing.md`（`libei1`、fingerprint、**Server 二重起動**に注意）。

診断: `koyori-diagnose-input-leap` / ma-home: `scripts/ma-home-input-leap-server.ps1`

ログオン自動起動: `.\scripts\install-input-leap-task.ps1`  

**日本語（Input Leap）**: 半/全 → **`'` リピート**の既知症状あり（使わない）。**Ctrl+Shift+Space**（Mozc）が本番。BT なら半/全可。

## タッチキーボード（onboard）— 保留

再有効化:

```bash
KOYORI_ONBOARD=1
KOYORI_OSK_BACKEND=onboard
sudo apt install -y onboard at-spi2-core
```
