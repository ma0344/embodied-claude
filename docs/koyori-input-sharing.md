# koyori 入力 — Keychron K4 MAX（Bluetooth）

Surface Go キオスクの入力は **Keychron K4 MAX の Bluetooth 切替** が本番。

| スロット | 接続先 | 切替 |
|---------|--------|------|
| **1** | ma-home (Windows) | `Fn+1` |
| **2** | koyori (Ubuntu) | `Fn+2` |
| **3** | 予備 | `Fn+3` |

**スロット 2 だけ koyori 専用**にする（他 PC と混ぜない）。

Input Leap / タッチ KB は見送り → `docs/backlog-koyori.md`

---

## MAC アドレスが毎回変わる

K4 MAX は **Bluetooth のランダムアドレス**（プライバシー）を使うことがある。
`bluetoothctl` で `Device XX:XX:... (random)` と出るのは正常。

- **ペアリング時**: そのとき見えている MAC で `pair` → `trust`（スクリプトは **名前で自動検出**）
- **再接続**: 固定 MAC を覚えなくてよい → `koyori-connect-keychron.sh`
- **何度も別 MAC で増殖**したら: `sudo koyori-bluetooth-cleanup-keychron.sh` してから再ペア

毎回 MAC を手入力する必要はない。

---

## 初回ペアリング

### キーボード

1. **USB を抜く**
2. **`Fn+2`**（koyori 専用スロット）
3. **`Fn+2` を約 3 秒長押し** → LED 速点滅
4. 見つからない: **`Fn+J+Z`**（Windows/Android）→ やり直し

### koyori

```bash
sudo apt install -y bluez
sudo systemctl enable --now bluetooth

cd ~/src/embodied-claude && git pull
koyori-pair-keychron.sh 2
```

スキャンで **`Keychron K4 Max`** を自動検出（既定パターン `K4 Max`）。
名前が違うとき: `KOYORI_KEYCHRON_NAME='Keychron' koyori-pair-keychron.sh 2`

`bluetoothctl devices` が空でも、スキャン中の `[NEW] Device ... Keychron K4 Max` 行から MAC を拾う。

手動:

```bash
bluetoothctl
power on
agent on
default-agent
scan on
# 名前で探す（MAC はそのときのものを使う）
pair AA:BB:CC:DD:EE:FF
trust AA:BB:CC:DD:EE:FF
connect AA:BB:CC:DD:EE:FF
quit
```

### 確認

webui 入力欄 → 英字 → **半/全** で日本語。

---

## 日常

1. **`Fn+2`** で koyori に接続
2. つながらない: `koyori-connect-keychron.sh`（SSH からでも可）

ma-home は **`Fn+1`**。

---

## つながらないとき

| 症状 | 対処 |
|------|------|
| scan に出ない | ペアリングモード（Fn+2 長押し）、USB 抜く、Fn+J+Z |
| 何個も Keychron が `devices` に溜まる | `sudo koyori-bluetooth-cleanup-keychron.sh` → 再ペア |
| ペア直後に切れる | `trust` 済みか。`sudo koyori-bluetooth-cleanup-keychron.sh` 後に再ペア |
| 再起動後に切れる | `koyori-connect-keychron.sh`。まだダメなら下記 IRK 回避 |
| スリープ後に切れる | GRUB: `btusb.enable_autosuspend=n`（install-koyori-kiosk の USB オプションと同様） |
| Windows と BT 併用 | **スロットを分ける**（Win=1, koyori=2）。同じスロットで両 OS ペアしない |

### ランダム MAC で再接続が壊れる場合（上級）

ペア後、まだ毎回ペアし直しなら（Ubuntu 24.04 で報告あり）:

```bash
# アダプタ MAC とキーボード MAC は環境依存
sudo systemctl stop bluetooth
sudo nano /var/lib/bluetooth/<adapter-mac>/<keyboard-mac>/info
# [IdentityResolvingKey] セクションを削除
sudo systemctl start bluetooth
```

詳細: [Arch Wiki Bluetooth](https://wiki.archlinux.org/title/Bluetooth)、Keychron Linux [gist](https://gist.github.com/andrebrait/961cefe730f4a2c41f57911e6195e444)

---

## 関連

- `scripts/koyori-kiosk/koyori-pair-keychron.sh`
- `scripts/koyori-kiosk/koyori-connect-keychron.sh`
- `docs/koyori-kiosk-ime.md` — 半/全 / Mozc
