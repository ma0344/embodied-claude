# koyori バックログ

ma-home 側の全体優先順・記憶 E2E: [backlog-ma-home.md](./backlog-ma-home.md)（2026-06-13 更新）。

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

## Input Leap — 見送り

tar.gz インストール・接続がうまくいかず諦め。コードは残す（`koyori-input-leap-start.sh`）。
`/etc/default/koyori-kiosk` で `KOYORI_INPUT_LEAP_SERVER` を未設定のまま = 無効。

## タッチキーボード（onboard）— 保留

再有効化:

```bash
KOYORI_ONBOARD=1
KOYORI_OSK_BACKEND=onboard
sudo apt install -y onboard at-spi2-core
```
