# koyori キオスク: 日本語入力 (IME)

Surface Go（koyori）の Chromium キオスクは `~/.xsession` から直接起動するため、
通常デスクトップの im-config / IBus 自動起動が走らない。**英字は打てるが日本語に切り替えられない**
状態になる。

## 対策（リポジトリ側）

- `koyori-ime-start.sh` — IBus + Mozc を起動し `mozc-jp` を選択
- `koyori-kiosk.sh` — Chromium の前に上記を source
- `install-koyori-kiosk.sh` — `ibus-mozc` を入れ、`im-config -n ibus` を user `ma` に設定

## koyori で適用

```bash
cd ~/src/embodied-claude/scripts/koyori-kiosk   # または scp したパス
git pull   # あれば
sudo ./install-koyori-kiosk.sh
sudo reboot
```

再起動後、webui の入力欄をクリックして **Ctrl+Space** で Mozc ON/OFF（IBus 既定）。

## 確認

```bash
grep ime /tmp/koyori-kiosk.log
# 例: ime: engine=mozc-jp

ibus list-engine | grep -i mozc
pgrep -u ma ibus-daemon
```

## うまくいかないとき

| 症状 | 対処 |
|------|------|
| ログに `ibus-daemon not found` | `sudo apt install -y ibus-mozc` → install スクリプト再実行 |
| `no mozc engine` | `ibus list-engine` の出力を確認。`ibus engine mozc-jp` を手動試行 |
| Ctrl+Space が効かない | 物理キーボード配列・Fn キー。`ibus-setup` でショートカット確認（SSH + `DISPLAY=:0`） |
| 変換候補が出ない | Chromium 再読み込み。`GTK_IM_MODULE=ibus` が効いているかログで確認 |

## 関連

- `docs/backlog-ma-home.md` — webui 常時起動（後で）
- `scripts/koyori-kiosk/koyori-kiosk.sh`
