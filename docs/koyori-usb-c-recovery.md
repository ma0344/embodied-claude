# koyori USB-C 復旧（Travel Hub / 有線 LAN）

Surface Go の USB-C が Linux で列挙されないときの手順。キオスクとは独立した **Type-C / UCSI** の問題。

## 症状

```bash
lsusb -t
# Bus 001: 内蔵 BT (0cf3:e302) のみ
# Bus 002: 空 — Travel Hub (045e) / Realtek LAN (0bda) が無い
ip -br link
# wlp1s0 のみ（有線 eth/enx* 無し）
```

UEFI ではキーボードが動く → ハードは生きている。OS 起動後に **UCSI（USB-C PD コントローラ）** が立ち上がっていないか、カーネル regression の可能性が高い。

## クイック復旧（koyori 上）

```bash
cd ~/src/embodied-claude/scripts/koyori-kiosk
sudo ./fix-usb-c.sh              # 診断
sudo ./fix-usb-c.sh reload       # UCSI モジュール再ロード
sudo ./fix-usb-c.sh reboot-hint  # 冷起動手順
```

### 1. UCSI 再ロード

```bash
sudo modprobe -r typec_ucsi
sleep 2
sudo modprobe typec_ucsi
lsusb -t
```

### 2. 冷起動 + ハブ先挿し

1. `sudo poweroff`（**reboot ではなく完全電源 OFF**）
2. Travel Hub を USB-C に挿したまま 5 秒待つ
3. 電源 ON → `lsusb -t`

### 3. 古いカーネルで起動（いちばん効くことが多い）

**注意:** `dpkg -l | grep surface` に **1 個しか無い** と GRUB に古い選択肢は出ない。先に旧版をインストールする。

```bash
# 入ってるイメージ（GRUB に出るのはこれだけ）
sudo ./fix-usb-c.sh list-kernels

# apt にある旧版一覧
sudo ./fix-usb-c.sh list-available

# 6.19 から一段下げて入れる（例）
sudo apt install linux-image-6.18.7-surface-1 linux-headers-6.18.7-surface-1
sudo update-grub
sudo reboot
```

再起動後: **GRUB → Advanced options for Ubuntu** → デフォルトの `6.19.8` ではなく **`6.18.7-surface-1` の行**を選ぶ → `lsusb -t`

まだダメならさらに下げる: `6.17.13-surface-2` など。

古いカーネルでハブが見えたら固定:

```bash
sudo apt-mark hold linux-image-surface linux-headers-surface
```

### 4. GUI なしで確認（キオスク切り分け）

```bash
sudo systemctl isolate multi-user.target
# SSH のまま Travel Hub を挿す
lsusb -t
```

ここで見える → graphical 起動後の電源管理が原因（稀）。  
ここでも見えない → カーネル / UCSI / 冷起動の問題。

## 成功時の見え方

```bash
lsusb -t
# Bus 002 以下に Hub、または
lsusb | grep -E '045e|0bda'
# 045e: Microsoft Travel Hub
# 0bda: Realtek USB Ethernet

ip -br link
# enx... または eth0 が UP
```

## キオスクとの関係

`install-koyori-kiosk.sh` は lightdm / graphical.target のみ。USB-C ドライバは触らない。  
同時期の **カーネル更新** と時期が重なったことが多い。

USB autosuspend  tweaks は **デフォルト無効**（`KOYORI_USB_POWER=1` のときのみ）。

## 関連スクリプト

| ファイル | 用途 |
|----------|------|
| `scripts/koyori-kiosk/fix-usb-c.sh` | 診断・UCSI reload・カーネル一覧 |
| `scripts/koyori-kiosk/diagnose-usb-c.sh` | 詳細ログ収集 |
| `scripts/koyori-kiosk/rollback-usb-extras.sh` | 誤って入れた USB extras の削除 |

## まだダメなとき

`sudo dmesg | grep -i ucsi` の全文を保存し、[linux-surface issues](https://github.com/linux-surface/linux-surface/issues) で `Surface Go` + `USB-C` を検索。  
一時回避: **Bluetooth キーボード** + **WiFi**（有線 LAN は USB-C 復旧まで待ち）。
