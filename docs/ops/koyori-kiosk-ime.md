# koyori キオスク: 日本語入力 (IME)

Surface Go（koyori）のキオスクは `~/.xsession` から直接起動するため、
通常デスクトップの im-config / IBus 自動起動が走らない。

キオスクは **Firefox + IBus/Mozc** を既定にしている（snap Chromium は IME 非推奨）。

## Input Leap 経由の日本語（2026-06-17 確認済み）

Input Leap は **半/全を転送しない**（JIS 専用キーが載らない）。届くときも **`'`（バッククォート）** として来る → **US 配列としてキー転送**されている。

### 本番: Mozc で **Ctrl+Shift+Space** をトグルに設定

Mozc プロパティ → General → Keymap → Customize → 2 エントリ追加:

| Mode | Key | Command |
|------|-----|---------|
| DirectInput | Ctrl Shift Space | Activate IME |
| Precomposition | Ctrl Shift Space | Deactivate IME |

（「Insert full-width space」等が同じショートカットなら削除/変更）

`ibus restart` または reboot 後、Input Leap 中に **Ctrl+Shift+Space** で あ↔A 切替。**動作確認済み。**

**既知**: 半/全は Input Leap 経由で **`'` が届く**（US 転送）。押しっぱなし／リピートで **`` 延々入力** することがある → **半/全は使わない**（Ctrl+Shift+Space で十分）。

### 予備: IBUS パネル

`ibus-setup` → Show property panel → **Always** → 画面上の **あ/A** をマウスでクリック（パネル切替も OK）。

### BT ドングル直結

半/全キーがそのまま効く（JIS 直結）。

### キーボード配列の図（Keyboard Viewer）

押したキーが光る **配列チャート**（参照用。マウスで入力はしない）:

```bash
sudo apt install -y gkbd-capplet   # 初回のみ
DISPLAY=:0 koyori-keyboard-layout      # 現在の XKB（jp）
DISPLAY=:0 koyori-keyboard-layout us   # US 図（Input Leap 転送の確認用）
```

フル GNOME なら設定アプリの「キーボード配列を表示」。キオスクは上記 CLI。

## 使い方（BT ドングル直結）

1. こよりの部屋（presence-ui `:8090`）の入力欄をクリック
2. **半/全キー**（JIS キーボードの Hankaku/Zenkaku）で日本語 ON/OFF
3. 日本語モードで入力

**Ctrl+Space / Super+Space は効かないことが多い**（最小 X セッションでは IBus の
ショートカットが未設定のため）。半/全が効けば正常。

## 起動時の IBus 警告ダイアログ

> At least one of your configured input methods does not exist in IBus input methods…

`gsettings` の `preload-engines` / `engines-order` に **`ibus list-engine` に無い名前**
（例: `mozc-on`）が入っていると出る。Ubuntu の `ibus-mozc` は通常 **`mozc-jp` のみ**。
`mozc-on` は Mozc の `ibus_config.textproto` 内ラベルで、IBus エンジン ID ではない。

**よくある2パターン:**

| 原因 | 例 |
|------|-----|
| 幽霊エンジン | `mozc-on` が preload に残っている |
| 早すぎる preload | daemon 起動時点で `mozc-jp` を書いたが Mozc 未登録 |

キオスクは `65koyori-ime-scrub`（`mozc-on` 等のみ除去）と `koyori-ime-start`（**ibus を殺さない**・Mozc 後に gsettings）で回避する。

**2026-06 回帰メモ:** 毎回 `preload=[]` + `ibus-daemon` 強制停止 + **Firefox より先に IME 同期** すると、snap Firefox が 1×1 ウィンドウのままになることがある。現行は **IME バックグラウンド → Firefox 先**。

確認:

```bash
DISPLAY=:0 ibus list-engine | grep -i mozc
DISPLAY=:0 gsettings get org.freedesktop.ibus.general preload-engines
DISPLAY=:0 gsettings get org.freedesktop.ibus.general engines-order
dconf dump /desktop/ibus/ | head -20
```

手当て:

```bash
sudo koyori-ime-preseed
# または
DISPLAY=:0 gsettings set org.freedesktop.ibus.general preload-engines "[]"
DISPLAY=:0 gsettings set org.freedesktop.ibus.general engines-order "[]"
sudo reboot
```

## ログの読み方

| ログ | 意味 |
|------|------|
| `ime: gsettings engines=['mozc-jp']` | **OK** — 実在エンジンのみ登録 |
| `ime: mozc registered; ... use 半/全` | **OK** — Mozc 登録済み。半/全で切替 |
| `ime: engine=mozc-jp` | **OK** — CLI でもエンジン選択できた |
| `ime: engine mozc-on failed` | **旧スクリプト** — `mozc-on` は IBus に無い。`git pull` + reinstall |
| `firefox launch:` の直後に `ERROR firefox process not found` | snap ラッパー即終了など — 最新 `koyori-kiosk.sh`（実 pid 待ち + 再起動ループ）を deploy |
| `firefox pid=` あってすぐ `firefox exited` | プロファイル lock / snap 起動失敗 — 下記「Firefox 手動起動」 |
| `ime: background timeout` | 旧スクリプト。半/全が効いていれば無視してよい |
| `ibus engine (current): xkb:us:eng` | 半/全を押すまで英字レイアウト表示のことがある |

```bash
grep ime /tmp/koyori-kiosk.log
DISPLAY=:0 koyori-diagnose-ime
DISPLAY=:0 ibus list-engine | grep -i mozc   # mozc-jp があれば OK
```

## セットアップ

```bash
cd ~/src/embodied-claude/scripts/koyori-kiosk
git pull
sudo ./install-koyori-kiosk.sh
sudo reboot
```

## ブラウザ・接続先

`/etc/default/koyori-kiosk`:

```bash
KOYORI_BROWSER=firefox    # 推奨
# 既定（フェーズ3）— 8080 直結ではない
KOYORI_WEBUI_URL='http://ma-home.local:8090/'
```

`This site can't be reached` のときは IPv4 リテラル（`http://192.168.x.x:8090/...`）を試す。
presence-ui と webui（8080）の両方が ma-home で起動していること。

## まだ日本語にならないとき

| 症状 | 対処 |
|------|------|
| 半/全でもダメ | `DISPLAY=:0 ibus list-engine \| grep mozc` が空 → `sudo apt install -y ibus-mozc` |
| `grep ime` が空 | `sudo ./install-koyori-kiosk.sh` して reboot |
| 英字キーボードのみ | JIS キーボード or 半/全相当キーがない |

## Firefox「profile cannot be loaded」

Ubuntu の Firefox（snap）は `/var/lib/...` のプロファイルを読めない。
キオスク用プロファイルは **ma のホーム配下** に置く:

- snap: `~/snap/firefox/common/.mozilla/koyori-kiosk`
- 通常: `~/.mozilla/koyori-kiosk`

`sudo ./install-koyori-kiosk.sh` で再インストール後 reboot。ログに
`firefox profile=...` が出れば OK。出ない場合はデフォルトプロファイルで
キオスク起動（全画面リサイズはそのまま効く）。

## 全画面（UI が左上の一部だけ）

Firefox `--kiosk` が物理画面いっぱいに伸びないことがある（右・下に黒帯）。
`install-koyori-kiosk.sh` は `xrandr` + `openbox` + `xdotool` でウィンドウを
ルート画面サイズに合わせる。

```bash
grep display /tmp/koyori-kiosk.log
# dimensions=1800x1200 resized window=... が出れば OK
```

まだ小さいときは `/etc/default/koyori-kiosk` に追加:

```bash
KOYORI_DISPLAY_MODE=1800x1200
```

## 入力

**Keychron K4 MAX** — `Fn+1` ma-home / `Fn+2` koyori。ペア: `koyori-pair-keychron.sh`（MAC は変わっても名前で検出）

→ [ops/koyori-input-sharing.md](../ops/koyori-input-sharing.md)

## 関連

- [ops/koyori-input-sharing.md](../ops/koyori-input-sharing.md)
- `docs/backlog-koyori.md`
- `docs/backlog-ma-home.md` — webui + presence-ui 常時起動（後で）
- `scripts/koyori-kiosk/koyori-kiosk.sh`
