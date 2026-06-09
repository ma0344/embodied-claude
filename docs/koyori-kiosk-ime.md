# koyori キオスク: 日本語入力 (IME)

Surface Go（koyori）のキオスクは `~/.xsession` から直接起動するため、
通常デスクトップの im-config / IBus 自動起動が走らない。

キオスクは **Firefox + IBus/Mozc** を既定にしている（snap Chromium は IME 非推奨）。

## 使い方（これが本番）

1. webui の入力欄をクリック
2. **半/全キー**（JIS キーボードの Hankaku/Zenkaku）で日本語 ON/OFF
3. 日本語モードで入力

**Ctrl+Space / Super+Space は効かないことが多い**（最小 X セッションでは IBus の
ショートカットが未設定のため）。半/全が効けば正常。

## ログの読み方

| ログ | 意味 |
|------|------|
| `ime: mozc registered; ... use 半/全` | **OK** — Mozc 登録済み。半/全で切替 |
| `ime: engine=mozc-jp` | **OK** — CLI でもエンジン選択できた |
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

## ブラウザ

`/etc/default/koyori-kiosk`:

```bash
KOYORI_BROWSER=firefox    # 推奨
```

## まだ日本語にならないとき

| 症状 | 対処 |
|------|------|
| 半/全でもダメ | `DISPLAY=:0 ibus list-engine \| grep mozc` が空 → `sudo apt install -y ibus-mozc` |
| `grep ime` が空 | `sudo ./install-koyori-kiosk.sh` して reboot |
| 英字キーボードのみ | JIS キーボード or 半/全相当キーがない |

## 関連

- `docs/backlog-ma-home.md` — webui 常時起動（後で）
- `scripts/koyori-kiosk/koyori-kiosk.sh`
