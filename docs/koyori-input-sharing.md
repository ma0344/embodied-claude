# koyori 入力 — Input Leap（優先）+ Keychron K4 MAX（予備）

**V5（2026-06-17）**: ma-home の物理 KB/マウスを **Input Leap** で koyori キオスクへ。  
ma-home = **Server (Windows)**、koyori = **Client (Ubuntu X11)**。

| 方式 | 用途 |
|------|------|
| **Input Leap** | 本番（2026-06-17 動作確認済み）— ma-home 右端から koyori へ |
| **Keychron BT** | 予備・持ち出し（`Fn+1` ma-home / `Fn+2` koyori） |

Input Leap 無効時は `KOYORI_INPUT_LEAP_SERVER` 未設定のまま → BT のみ。

**動いている構成（LAN）**: 両方 `--disable-crypto`。Server は **1 プロセスだけ**。

**日本語（確認済み）**: Input Leap は半/全を **`'`** として転送（US 配列扱い）。**Mozc プロパティで Ctrl+Shift+Space** を IME トグルに設定 → キーボードで切替可。IBUS パネル あ/A も可。BT なら半/全。→ `docs/koyori-kiosk-ime.md`

**再起動後**: koyori はキオスク起動時に client + **watch**（30s ごとに再起動）。ma-home Server は `install-input-leap-task.ps1`（ログオン時）。Surface だけ先に起動すると数分待つか watch が拾う。

---

## Input Leap — Phase 1（koyori client）

### 1. バイナリ + 依存関係

```bash
cd ~/src/embodied-claude/scripts/koyori-kiosk
# tarball は GitHub releases から /tmp へ
sudo ./install-input-leap-tarball.sh /tmp/input-leap-ubuntu-24-04-v3.0.3.tar.gz
```

`libei.so.1` エラーが出たら:

```bash
sudo apt-get install -y libei1 libportal1
/usr/local/bin/input-leapc --help | head -3
```

### 2. 設定

`/etc/default/koyori-kiosk`:

```bash
KOYORI_INPUT_LEAP_SERVER='192.168.x.x'   # ma-home LAN IP（または Tailscale）
KOYORI_INPUT_LEAP_NAME='koyori'          # Windows Server の画面名と完全一致
# KOYORI_INPUT_LEAP_CRYPTO=0             # 既定 OFF（LAN 向け。1 にすると fingerprint + 双方向 cert が必要）
```

### 3. 診断・再起動

```bash
koyori-diagnose-input-leap
sudo reboot
```

### 4. ma-home（Phase 2）

1. `C:\Programs\InputLeap` に zip 展開（インストーラ不要）
2. **Server は GUI ではなく CLI**（zip 版は `input-leapd` サービス未登録 → GUI が IPC エラーになる）

```powershell
# 古い Server を全部止めてから1つだけ起動（複数起動すると証明書エラーが続く）
Get-Process input-leaps -ErrorAction SilentlyContinue | Stop-Process -Force
cd C:\Programs\InputLeap
.\input-leaps.exe -c .\default.sgc --disable-client-cert-checking --disable-crypto
```

LAN なら **`--disable-crypto`** 推奨（fingerprint / クライアント証明書不要）。  
crypto 有効時は Server に `--disable-client-cert-checking` が必須。

3. Firewall: TCP **24800** 許可（済ならスキップ）

```powershell
New-NetFirewallRule -DisplayName "Input Leap" -Direction Inbound -Protocol TCP -LocalPort 24800 -Action Allow
```

4. **Server の SSL フィンガープリントを koyori に信頼登録**（crypto 有効時は必須）

ma-home:

```powershell
Get-Content "$env:LOCALAPPDATA\InputLeap\SSL\Fingerprints\Local.txt"
```

koyori:

```bash
koyori-input-leap-trust-server - <<'EOF'
v2:sha1:....   # Local.txt の行をそのまま貼る
v2:sha256:....
EOF
pkill -u ma -f 'input-leapc.*192.168.10.100' || true
/usr/local/bin/koyori-input-leap-start   # キオスク再起動でも可
koyori-diagnose-input-leap
```

永続化するなら `/etc/koyori-kiosk/input-leap-server-fingerprint.txt` に同じ2行を置く（キオスク起動時に自動反映）。

`ScrollLock` hotkey の WARNING は無視してよい。

### 5. ma-home ログオン自動起動

```powershell
cd C:\Users\ma\src\embodied-claude
.\scripts\install-input-leap-task.ps1
```

ログ: `%USERPROFILE%\.config\embodied-claude\logs\input-leap-server.log`  
解除: `.\scripts\install-input-leap-task.ps1 -Uninstall`

`scripts\input-leap\default.sgc` を `C:\Programs\InputLeap\` にコピーして使う。

### 6. Mouse Without Borders との関係

| ツール | 対象 | ma-home での扱い |
|--------|------|------------------|
| **Input Leap** | ma-home → **koyori (Linux)** | 本番 |
| **Mouse Without Borders** | **Windows ↔ Windows のみ** | koyori には届かない |

両方とも ma-home で KB/マウスをフックするので、**同時に有効にすると端で取り合い**になることがある。  
koyori 用は Input Leap だけにして、MWB は他の Windows PC 用なら **使うときだけ ON** が安全。

### 7. 日本語入力（IME）

Input Leap は **Windows の MS-IME の変換状態を koyori に渡さない**（生のキーだけ）。  
koyori 側で **IBus + Mozc** が別途必要（`install-koyori-kiosk.sh` が入れる）。

**手順（koyori 画面にマウスが入ったあと）:**

1. 診断: `koyori-diagnose-ime`（`ibus-mozc` / `ibus-daemon` / `mozc-jp`）
2. ブラウザは **Firefox** 推奨: `/etc/default/koyori-kiosk` に `KOYORI_BROWSER=firefox`
3. **Mozc をオン** — JIS キーボードなら **半/全**（Hankaku/Zenkaku）
4. ma-home が **日本語配列**なら koyori も **JIS** に合わせる（既定 / Input Leap 時は自動 `jp`）:

```bash
# /etc/default/koyori-kiosk
KOYORI_XKB_LAYOUT=jp
```

5. koyori 画面にフォーカスしたあと **そのままローマ字入力**（`konnichiwa` + Space）  
   Input Leap 有効時は `ibus_config.textproto` で **ひらがな常時 ON**（半/全・Ctrl+Space 不要）

6. **ローマ字入力**（Mozc ROMAN）: `konnichiwa` + Space → こんにちは  

7. BT ドングル直結のときだけ **半/全** で英数 ↔ 日本語を切替可能

---

## Keychron K4 MAX（Bluetooth 予備）

koyori キオスクの BT 入力は **Keychron K4 MAX の Bluetooth 切替**。

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

1. **`Fn+2`** で koyori スロットへ（接続まで数秒かかることあり）
2. つながらない: `koyori-connect-keychron.sh`（**Fn+2 を押してから**実行）
3. キオスクは 30 秒ごとに自動再接続（`KOYORI_BT_AUTOCONNECT=1`）

ma-home は **`Fn+1`**。スロット 2 は koyori 専用に。

### Fn+2 だけでは繋がらない

```bash
cd ~/src/embodied-claude/scripts/koyori-kiosk
sudo ./install-koyori-kiosk.sh    # BlueZ ReconnectUUIDs
sudo systemctl restart bluetooth
koyori-connect-keychron.sh        # Fn+2 押しながら/直後に
grep bt-watch /tmp/koyori-kiosk.log
```

---

## つながらないとき

| 症状 | 対処 |
|------|------|
| `Paired: no` / agent エラー | 最新 `koyori-pair-keychron.sh`（pair 後 20s 待機）。**Fn+2 点滅を pair 完了まで維持** |
| scan に出ない | ペアリングモード（Fn+2 長押し）、USB 抜く、Fn+J+Z |
| 何個も Keychron が `devices` に溜まる | `sudo koyori-bluetooth-cleanup-keychron.sh` → 再ペア |
| ペア直後に切れる | `koyori-connect-keychron.sh` |
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
