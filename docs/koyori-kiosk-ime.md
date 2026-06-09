# koyori キオスク: 日本語入力 (IME)

Surface Go（koyori）の Chromium キオスクは `~/.xsession` から直接起動するため、
通常デスクトップの im-config / IBus 自動起動が走らない。**英字は打てるが日本語に切り替えられない**
状態になる。

加えて Ubuntu 24.04 の **snap 版 Chromium はホスト IBus を使えない**ことが多い。
キオスクは **Firefox + IBus/Mozc** を既定にしている。

## 症状から読み取る

| 確認結果 | 意味 |
|----------|------|
| `grep ime /tmp/koyori-kiosk.log` が空 | IME スクリプト未導入、または古い `koyori-kiosk` |
| `ibus list-engine` に mozc が無い | `ibus-mozc` 未インストール、または SSH から DISPLAY 未指定 |
| `pgrep ibus-daemon` だけ動く | デーモンはいるが Mozc エンジン未登録 |

SSH から IBus を見るときは **必ず DISPLAY を付ける**:

```bash
DISPLAY=:0 koyori-diagnose-ime
# または
DISPLAY=:0 XDG_RUNTIME_DIR=/run/user/$(id -u) ibus list-engine | grep -i mozc
```

## 対策（リポジトリ側）

- `koyori-ime-start.sh` — IBus 再起動 + Mozc 選択（ログは `/tmp/koyori-kiosk.log` に `ime:`）
- `koyori-kiosk.sh` — Chromium 前に IME 起動。**既定ブラウザ Firefox**
- `install-koyori-kiosk.sh` — `ibus-mozc` / `ibus-gtk3` / `firefox` 等を導入
- `koyori-diagnose-ime` — 一括診断

## koyori で適用

```bash
cd ~/src/embodied-claude/scripts/koyori-kiosk
git pull
sudo ./install-koyori-kiosk.sh
sudo reboot
```

再起動後:

```bash
grep ime /tmp/koyori-kiosk.log
# 例:
# ime: start DISPLAY=:0 uid=1000
# ime: engine=mozc-jp
# browser=firefox (KOYORI_BROWSER=firefox)
```

webui の入力欄をクリック → **Ctrl+Space** で Mozc ON/OFF。

## ブラウザを変えたい

`/etc/default/koyori-kiosk`:

```bash
KOYORI_BROWSER=firefox    # 推奨（日本語入力）
# KOYORI_BROWSER=chromium   # snap だと IME が効かないことが多い
# KOYORI_BROWSER=auto       # firefox があれば firefox 優先
```

変更後: `sudo reboot`

## うまくいかないとき

| 症状 | 対処 |
|------|------|
| `grep ime` が空 | `sudo ./install-koyori-kiosk.sh` を再実行して reboot |
| `ERROR ibus-mozc not installed` | `sudo apt install -y ibus-mozc ibus-gtk3 firefox` |
| `no mozc engine` | `koyori-diagnose-ime` の engines 行を確認 |
| Ctrl+Space が効かない | 入力欄フォーカス確認。Fn キーで Ctrl が効いているか |
| Firefox でもダメ | `journalctl -u lightdm -b` と `/tmp/koyori-kiosk.log` を共有 |

## 関連

- `docs/backlog-ma-home.md` — webui 常時起動（後で）
- `scripts/koyori-kiosk/koyori-kiosk.sh`
