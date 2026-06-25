# koyori キオスク: Firefox 表示・`--kiosk` 切り分け

Surface Go（snap Firefox + openbox 最小 X）向け。

## 2026-06 回帰の整理

| 時期 | 状態 |
|------|------|
| 音量オーバーレイ確認時 | UI 表示 OK（`--kiosk` あり） |
| IBus 修正（preload 毎回 `[]` + **ibus kill** + **IME が Firefox より先**） | 1×1 ウィンドウ・真っ黒 |
| 現行（IME 並行・ibus 維持・openbox rc 修正・再起動ループ修正） | UI OK、`KIOSK_FLAG=0` だとタブバーが出る |

**壊したのは `--kiosk` 単体ではなく、起動順 + ibus 再起動 + openbox rc 壊れ** が重なったこと。

## 推奨: 段階的に `--kiosk` を戻す

`/etc/default/koyori-kiosk` で切替。変更後は `sudo reboot` か `pkill firefox`（キオスクが1プロセスだけ上げ直す）。

### Stage A — 表示優先（タブバーが出る）

```bash
KOYORI_FIREFOX_KIOSK_FLAG=0
```

確認: `grep 'firefox launch' /tmp/koyori-kiosk.log` に `--kiosk` が **無い**。

### Stage B — 本番（タブバー非表示）※ install 既定

```bash
KOYORI_FIREFOX_KIOSK_FLAG=1
```

openbox rc が有効なこと（Syntax Error ダイアログが出ないこと）が前提。

確認:

```bash
DISPLAY=:0 koyori-diagnose-browser
grep -E 'firefox launch|display: browser' /tmp/koyori-kiosk.log | tail -5
```

期待:

- `firefox launch: firefox --profile ... --kiosk http://...`
- `display: browser primary=... geometry=1800x1200+0+0`

### Stage B で 1×1 / 真っ黒のとき

1. **IME が Firefox より先に同期実行されていないか**（ログで `firefox launch` が `ime: background` より **後**）
2. **`ime: stopping existing ibus-daemon` が出ていないか**（出たら `KOYORI_IME_FORCE_RESTART` が 1）
3. ウィンドウ幾何:

```bash
for wid in $(DISPLAY=:0 xdotool search --class Firefox); do
  echo -n "$wid "; DISPLAY=:0 xdotool getwindowgeometry --shell "$wid" | grep -E 'WIDTH|HEIGHT'
done
```

4. 応急: Stage A に戻す（`KOYORI_FIREFOX_KIOSK_FLAG=0`）
5. 最終手段: `KOYORI_FIREFOX_SOFTWARE_GL=1`（GPU 黒画面時）

## 起動時の白画面 + 左上の黒四角

多くは **openbox 読込前 / Firefox 初回マップ前** の一瞬（旧 1×1 ウィンドウ or 黒 `xsetroot`）。

- openbox rc を直したうえで Stage B を試す
- キオスクはルート背景を presence-ui に合わせ `#f5f5f0` に変更済み
- 数秒で全画面になれば許容；ずっと残るなら Stage B 失敗 → 上記 1×1 切り分け

## タブが増える

`grep 'firefox launch' /tmp/koyori-kiosk.log` が **2分おき** に出ていたら、旧スクリプト（120秒 wait 打ち切り）。  
最新 `koyori-kiosk.sh` では Firefox 終了まで待ち、二重起動しない。

## 関連コマンド

```bash
DISPLAY=:0 koyori-diagnose-browser
DISPLAY=:0 koyori-fix-browser-window
DISPLAY=:0 koyori-restart-browser
grep -E 'ime:|firefox |display:' /tmp/koyori-kiosk.log | tail -30
```

## install 後チェックリスト

```bash
cd ~/src/embodied-claude/scripts/koyori-kiosk
sudo ./install-koyori-kiosk.sh
xmllint --noout ~/.config/openbox/rc.xml   # Syntax Error 防止
sudo reboot
```
