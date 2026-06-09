# koyori 入力 — Keychron K2（Bluetooth）

Surface Go キオスクの入力は **Keychron K2 の Bluetooth 切替** が本番。

| チャンネル | 接続先 | 切替 |
|-----------|--------|------|
| **1** | ma-home (Windows) | `Fn+1` |
| **2** | koyori (Ubuntu) | `Fn+2` |
| **3** | （予備） | `Fn+3` |

Input Leap / タッチキーボードは見送り → `docs/backlog-koyori.md`

---

## 初回ペアリング（koyori）

### 1. キーボード側

1. **有線 USB を抜く**（BT ペアリング中はケーブル外す）
2. **`Fn+2`** でスロット 2 を選ぶ
3. **`Fn+2` を約 3 秒長押し** → LED が速く点滅（ペアリングモード）
4. 見つからないとき: **`Fn+J+Z`**（Windows/Android モード）を押してから 2〜3 をやり直す

### 2. koyori 側

```bash
sudo apt install -y bluez
sudo systemctl enable --now bluetooth

cd ~/src/embodied-claude/scripts/koyori-kiosk
./koyori-pair-keychron.sh 2
```

対話式。15 秒スキャン後、表示された Keychron の **MAC アドレス** を貼る。

手動でやる場合:

```bash
bluetoothctl
power on
agent on
default-agent
scan on
# "Keychron K2" が出たら:
pair AA:BB:CC:DD:EE:FF
trust AA:BB:CC:DD:EE:FF
connect AA:BB:CC:DD:EE:FF
scan off
quit
```

### 3. 動作確認

- キオスクの webui で入力欄をクリック
- 英字が打てるか
- **半/全** で日本語（Mozc）に切替

```bash
DISPLAY=:0 koyori-diagnose-ime
```

---

## 日常の使い方

1. Surface の前に立つ
2. K2 で **`Fn+2`**（koyori に接続。LED が青などで点灯）
3. 打てないとき: もう一度 `Fn+2`、または SSH から `bluetoothctl connect <MAC>`

ma-home に戻るときは **`Fn+1`**。

---

## つながらないとき

| 症状 | 対処 |
|------|------|
| scan に出ない | キーボードのペアリングモード（Fn+2 長押し）をやり直す。USB 抜く |
| pair 失敗 | 他デバイスのペアリングを解除。K2 を工場リセット（マニュアル参照）して再ペア |
| 再起動後に切れる | `trust` 済みか確認。`bluetoothctl connect <MAC>` |
| 英字だけ / 日本語不可 | webui 入力欄フォーカス → **半/全** |
| `bluetooth` が無い | `sudo apt install bluez && sudo systemctl start bluetooth` |

保存した MAC の確認:

```bash
cat ~/.config/koyori-keychron-mac 2>/dev/null
bluetoothctl devices
```

---

## 関連

- `docs/koyori-kiosk-ime.md` — Mozc / 半/全
- `docs/backlog-koyori.md` — Input Leap / タッチ KB（見送り）
- `scripts/koyori-kiosk/koyori-pair-keychron.sh`
