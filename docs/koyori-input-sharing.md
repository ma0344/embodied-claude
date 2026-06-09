# koyori 入力共有（Input Leap + Keychron Bluetooth）

Surface Go キオスクの入力は **物理キーボード** 前提。

| 手段 | 用途 |
|------|------|
| **Keychron K2 Bluetooth** | 接続先を 1/2/3 で切替（いちばん単純） |
| **Input Leap** | デスクに座ったまま、マウスを画面端へ寄せて koyori を操作 |

タッチキーボード（onboard）は保留 → `docs/backlog-koyori.md`

---

## Keychron K2（Bluetooth 切替）

1. **チャンネル 1** — ma-home（Windows）とペアリング  
2. **チャンネル 2** — koyori（Ubuntu）とペアリング  
3. 使うとき `Fn+1` / `Fn+2` で切替（機種により `Fn+Q/W/E`）

koyori 側:

```bash
# Bluetooth 設定（初回のみ）
bluetoothctl
# power on
# scan on
# pair <MAC>
# trust <MAC>
# connect <MAC>
```

キオスクで日本語: webui 入力欄をクリック → **半/全** で Mozc ON。

---

## Input Leap — ma-home (Windows Server) → koyori (Client)

```
[ma-home Windows]  Keychron K2（USB または BT）
       Server
            │  LAN または Tailscale（推奨）
       Client
[koyori Ubuntu]  Firefox キオスク
```

マウスを ma-home モニタの **koyori 側の端** に寄せると、Surface 上で操作できる。

### 1. ma-home (Windows) — Server

1. [Input Leap Releases](https://github.com/input-leap/input-leap/releases) → Windows インストーラ
2. 起動 → **Server** を選択
3. **Configure Server** でスクリーン配置:
   - 左: `ma-home`（この PC）
   - 右: `koyori`（スクリーン名は **完全一致**）
4. **Start**（Server 実行中のまま）

Tailscale IP（推奨）:

```powershell
tailscale ip -4
```

ファイアウォール（管理者 PowerShell）:

```powershell
New-NetFirewallRule -DisplayName "Input Leap" `
  -Direction Inbound -Protocol TCP -LocalPort 24800 -Action Allow
```

### 2. koyori (Ubuntu) — Client

v3.0.3 は **.deb ではなく tar.gz** のみ（中にさらに tar が入っている）。

```bash
# 例: /tmp/input-leap-ubuntu-24-04-v3.0.3.tar.gz を置いた状態で
cd ~/src/embodied-claude/scripts/koyori-kiosk
sudo ./install-input-leap-tarball.sh /tmp/input-leap-ubuntu-24-04-v3.0.3.tar.gz
input-leapc --help
```

手動でやる場合:

```bash
cd /tmp
tar xzf input-leap-ubuntu-24-04-v3.0.3.tar.gz
cd input-leap-ubuntu-24-04
tar xf input-leap-ubuntu-24-04.tar.gz    # 内側は gzip ではない plain tar
sudo cp -a input-leap-ubuntu-24-04/bin/* /usr/local/bin/
sudo cp -a input-leap-ubuntu-24-04/share/. /usr/local/share/
sudo apt install -y libqt6core6t64 libqt6gui6t64 libqt6widgets6t64 libssl3
```

別案: [Flathub Input Leap](https://flathub.org/apps/io.github.input_leap.input-leap)（GUI 用。キオスクの CLI client とは別）。

`/etc/default/koyori-kiosk` を編集（**install で上書きされるので、その後に設定**）:

```bash
sudo nano /etc/default/koyori-kiosk
```

```bash
# ma-home の Tailscale IP（例）
KOYORI_INPUT_LEAP_SERVER='100.64.x.x'
KOYORI_INPUT_LEAP_NAME='koyori'
KOYORI_INPUT_LEAP_CRYPTO=1
```

キオスクスクリプトを最新に:

```bash
cd ~/src/embodied-claude/scripts/koyori-kiosk
sudo ./install-koyori-kiosk.sh
sudo reboot
```

### 3. 確認

```bash
koyori-diagnose-input-leap
grep input-leap /tmp/koyori-kiosk.log
```

成功例:

```
input-leap: client name=koyori server=100.64.x.x pid=...
```

ma-home でマウスを右端へ → koyori の Surface でカーソルが動けば OK。

### 4. つまずきやすい点

| 症状 | 対処 |
|------|------|
| Client が繋がらない | Server が Start 済みか、IP が Tailscale/LAN で届くか、`24800` が開いているか |
| スクリーン名不一致 | Server 配置の名前と `KOYORI_INPUT_LEAP_NAME` を一致（既定 `koyori`） |
| crypto エラー | 両方 `--enable-crypto`（既定）。ダメなら `KOYORI_INPUT_LEAP_CRYPTO=0` を両側で |
| 日本語がおかしい | **半/全** は Server 側キーボードから送られる。おかしければ K2 を koyori BT に直接切替 |
| `input-leapc not installed` | `install-input-leap-tarball.sh` で tar.gz から `/usr/local/bin` へ |

---

## 関連

- `docs/koyori-kiosk-ime.md` — Mozc / 半/全
- `docs/backlog-koyori.md` — タッチキーボード（保留）
- `scripts/koyori-kiosk/koyori-input-leap-start.sh`
