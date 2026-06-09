# koyori バックログ

## 本番: Keychron K2 Bluetooth

手順: `docs/koyori-input-sharing.md`  
スクリプト: `scripts/koyori-kiosk/koyori-pair-keychron.sh`

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
