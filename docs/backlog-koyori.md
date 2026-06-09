# koyori バックログ

## タッチキーボード（onboard）— 保留

florence は環境によりインストール不可。onboard は動くが Firefox 全画面との
相性調整が必要（dock-expand オフ、xdotool 再配置など）。コードは
`scripts/koyori-kiosk/koyori-onboard-start.sh` に残す。

再有効化:

```bash
# /etc/default/koyori-kiosk
KOYORI_ONBOARD=1
KOYORI_OSK_BACKEND=onboard
```

```bash
sudo apt install -y onboard at-spi2-core
sudo reboot
```

## Input Leap + Keychron — 進行中

手順: `docs/koyori-input-sharing.md`
