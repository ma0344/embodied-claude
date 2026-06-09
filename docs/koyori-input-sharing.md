# koyori 入力まわり（Input Leap + タッチキーボード）

Surface Go キオスク向け。物理キーボードが無い／遠いときの入力手段。

## 1. Input Leap — ma-home (Windows) のキーボードを共有

**Windows から共有できる。** ma-home を **Server**、koyori を **Client** にする。

```
[ma-home Windows]  Keychron K2 など
       Server (input-leaps)
            │  LAN または Tailscale
       Client (input-leapc)
[koyori Ubuntu]  Firefox キオスク
```

マウスを ma-home 画面の端（koyori 側）へ寄せると、koyori の Surface で操作できる。

### ma-home (Windows)

1. [Input Leap Releases](https://github.com/input-leap/input-leap/releases) から Windows 用をインストール
2. **Server** モードを選択
3. 画面配置で **koyori** スクリーンを追加（実際の置き方に合わせて左右をドラッグ）
4. koyori 側のスクリーン名は **`koyori`**（`/etc/default/koyori-kiosk` の `KOYORI_INPUT_LEAP_NAME` と一致させる）
5. Server を Start
6. ファイアウォールで Input Leap（既定 TCP **24800** 付近）を LAN/Tailscale から許可

Tailscale だけで繋ぐ場合は、Server の IP に **ma-home の Tailscale IP**（例 `100.x.x.x`）を使う。

### koyori (Ubuntu)

```bash
# .deb が無い場合は Releases から Ubuntu 24.04 用を取得
sudo apt install -y ./input-leap*.deb   # または GitHub から

cd ~/src/embodied-claude/scripts/koyori-kiosk
sudo ./install-koyori-kiosk.sh
```

`/etc/default/koyori-kiosk` を編集:

```bash
# ma-home の LAN IP または Tailscale IP
KOYORI_INPUT_LEAP_SERVER='100.64.x.x'
KOYORI_INPUT_LEAP_NAME='koyori'
```

```bash
sudo reboot
grep input-leap /tmp/koyori-kiosk.log
# input-leap: client name=koyori server=...
```

### 日本語 IME

- koyori 側 Firefox + Mozc はそのまま使える想定
- 半/全は **Server 側の物理キーボード**から koyori に送られる
- おかしければ Keychron の Bluetooth 切替（下記）にフォールバック

### Keychron K2（Bluetooth 切替）

Input Leap なしでも、K2 の **1/2/3 チャンネル**で ma-home ↔ koyori を切り替え可能。  
「1台のキーボードでマウス移動だけ切替」が Input Leap、「接続先ごと切替」が Bluetooth。

---

## 2. タッチキーボード（onboard）

キオスク既定で **onboard** を起動する（`KOYORI_ONBOARD=1`）。

| 操作 | 説明 |
|------|------|
| 入力欄タップ | 自動でキーボード表示（tablet-mode） |
| 画面端のパレットアイコン | 手動で表示/非表示 |
| 日本語 | 入力欄フォーカス後、**半/全**または Mozc で変換（物理 KB と同じ） |

無効化:

```bash
# /etc/default/koyori-kiosk
KOYORI_ONBOARD=0
```

高さ変更: `KOYORI_ONBOARD_HEIGHT=260`

ログ:

```bash
grep onboard /tmp/koyori-kiosk.log
```

---

## 関連

- `docs/koyori-kiosk-ime.md` — Mozc / 半/全
- `scripts/koyori-kiosk/koyori-kiosk.sh`
