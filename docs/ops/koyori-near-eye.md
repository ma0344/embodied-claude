# koyori 近目 — こよりフロントエンドの「目」

Surface Go（`koyori.local`）のフロントカメラを、こよりの **近目センサー** として使う。
部屋向け Tapo（`wifi-cam-mcp`）= **遠目**、koyori 内蔵 cam = **近目**（キオスク前・顔・手元）。

## 役割分担

| 機体 | 役割 | 目 |
|------|------|-----|
| **koyori** (Surface Go, Ubuntu) | 常時オン sensory フロントエンド | 近目キャプチャ + 将来 UI |
| **ma-home** (Windows, LM Studio) | 脳・MCP・Claude Code | vision describe / 記憶 / 会話 |
| **Tapo C200** | 部屋全体 | 遠目（既存 `wifi-cam-mcp`） |

Tailscale / LAN で koyori ↔ ma-home を接続する。

### 利用スコープ（確定 2026-07-14 · B'）

**本命は speak / miss_companion の在席信号。** 観察・記憶の主ソースにはしない。

| 項目 | 決め |
|------|------|
| speak 許可 | **near（キオスク前）OR far（Tapo・部屋）** |
| ゲート順 | **near 先 → 不在なら far 救済** |
| near キャプチャ | **喋り直前の需要駆動 · fresh 1枚**（ゲート用は caption / remember しない） |
| refresh timer | **既定 OFF**（Surface カメラ LED がうざい）· unit は残置・手動 enable 可 |
| チャット「見て」 | デフォ **遠目**。near は机/手元/キオスク明示時のみ → そのときだけ caption±remember |
| desire | `look_near` で **満たさない** |

**やらない:** 自律 tick の定常 `look_near`、near を「見て」既定 / joint attention / 記憶の主ソース、`/see-near` MCP、ゲート経路の自動 remember。

次の実装スライス: ✅ speak / miss_companion 在席ゲート（near fresh struct present → far 救済 · fail-closed）。
やらない当面: 自律の定常 look_near、会話「見て」近目既定、ゲート自動 remember、chat TTS / remind へのゲート拡張。

---

## koyori 側（確定済み前提）

### ハード・BIOS

- Surface Go 初代、SSD、有線、`koyori.local`
- **フロント cam のみ ON**、リア・IR OFF（同時 ON は libcamera 0 台になりやすい）
- **Secure Boot OFF**（`linux-surface` カーネル用）

### OS・パッケージ

- `linux-image-surface`（例: `6.19.8-surface-3`）
- GRUB: `acpi_enforce_resources=lax`
- `libcamera-ipa`, `libcamera-tools`, `gstreamer1.0-libcamera`, `gstreamer1.0-plugins-good`, `gstreamer1.0-tools`
- ユーザー `ma` は `video` グループ

### キャプチャ方式（**GStreamer のみ**）

- **使う:** `libcamerasrc` → `jpegenc`（IPA 経由で実写が取れる）
- **使わない（主経路）:** `cam` 生 NV12 → ffmpeg（stride/緑画面/暗さの理由で非推奨）
- **GStreamer ライブ**は将来キオスクプレビュー用に温存

脚本: [`scripts/koyori-capture.sh`](../scripts/koyori-capture.sh)

```bash
sudo install -m 755 scripts/koyori-capture.sh /usr/local/bin/koyori-capture

# 通常
koyori-capture /var/lib/koyori/latest.jpg

# 暗室（AE 収束待ち）
KOYORI_PICK_FRAME=12 KOYORI_CAPTURE_TIMEOUT=18 koyori-capture /var/lib/koyori/latest.jpg
```

### 露出（AE）について

- 起動直後数秒は暗い。**自動露出が安定するまで待つ**必要がある
- 暗いほど収束が遅い → `KOYORI_CAPTURE_TIMEOUT` / `KOYORI_PICK_FRAME` を大きくする
- 将来: 常時薄い GStreamer プレビューで AE を温め、`koyori-capture` は最新フレームだけ拾う

---

## 実装ロードマップ

### Phase 1 — koyori 上で JPEG を公開 ✅

koyori が **最新1枚** を保持し、HTTP で返す。

```
koyori-capture → /var/lib/koyori/latest.jpg
       ↑
GET /see 同期 capture（ゲート・明示時）※ timer は既定 OFF
       ↓
koyori-see-http (:8765)
  GET http://koyori.local:8765/health
  GET http://koyori.local:8765/latest.jpg
  GET http://koyori.local:8765/see        → capture してから返す（同期）
```

配置:

| パス | 役割 |
|------|------|
| `/usr/local/bin/koyori-capture` | GStreamer JPEG キャプチャ |
| `/usr/local/bin/koyori-see-http` | HTTP + `--refresh` |
| `/var/lib/koyori/latest.jpg` | 直近キャプチャ（オンデマンド） |
| `/etc/default/koyori-see` | 任意 override（暗所用 timeout 等） |
| `koyori-see-http.service` | HTTP 常駐 |
| `koyori-capture-refresh.timer` | 任意（既定 disable · LED 回避） |

既に timer が動いてる koyori では:

```bash
sudo systemctl disable --now koyori-capture-refresh.timer
```

**koyori への install:**

```bash
cd ~/src/embodied-claude
git pull
cd scripts/koyori-kiosk
sudo ./install-koyori-near-eye.sh
```

**確認（ma-home から）:**

```bash
curl -fsS http://koyori.local:8765/health
curl -fsS -o latest.jpg http://koyori.local:8765/latest.jpg
curl -fsS -o see.jpg http://koyori.local:8765/see   # 数秒待つ
```

暗所で暗いときだけ `/etc/default/koyori-see` に:

```bash
KOYORI_PICK_FRAME=12
KOYORI_CAPTURE_TIMEOUT=18
```

→ `sudo systemctl restart koyori-see-http.service`

### Phase 2 — ma-home から取得 ✅（gateway 本線）

**方針:** 新 MCP は作らない。`presence-ui` が koyori `:8765` を pull（gateway-direct と整合）。

| API | 動作 |
|-----|------|
| `GET /api/v1/near-camera/health` | koyori `/health` をプロキシ |
| `GET /api/v1/near-camera/snapshot` | `/latest.jpg`（既定）を取得 → base64 JSON |
| `.../snapshot?fresh=1` | koyori `/see`（同期キャプチャ・遅い） |
| `.../snapshot?describe=1` | LM Studio vision caption 付き |

環境変数（`presence-ui.local.env`）:

```env
KOYORI_CAM_URL=http://koyori.local:8765
# PRESENCE_NEAR_CAMERA_TIMEOUT_SECONDS=8
# PRESENCE_NEAR_CAMERA_SEE_TIMEOUT_SECONDS=25
# PRESENCE_NEAR_CAMERA_REFRESH=0   # 1 なら常に /see
# PRESENCE_NEAR_CAMERA_DESCRIBE=0  # 1 なら既定で caption
```

**スモーク（ma-home）:**

```powershell
curl.exe -fsS http://127.0.0.1:8090/api/v1/near-camera/health
curl.exe -fsS "http://127.0.0.1:8090/api/v1/near-camera/snapshot" | Select-Object -First 1
# 任意: caption
curl.exe -fsS "http://127.0.0.1:8090/api/v1/near-camera/snapshot?describe=1"
```

実装: `presence_ui/services/near_camera.py` · 変更後は `.\scripts\restart-presence-ui.ps1`

**後回し（任意）:** Surface Direct JPEG 直渡し、専用 visual-memory schema、チャット「見て」far 導線の明示配線。

### Phase 3 — gateway 行動配線 ✅（最小 · MCP slash 見送り）

**方針:** `/see-near` MCP は作らない。`smoke_action=look_near` → `look_near_direct()`。

| ステップ | 内容 |
|----------|------|
| pull | `fetch_near_camera_snapshot(describe=True)`（既定 `/latest.jpg`） |
| remember | `[near_eye source=koyori]` + caption（observation） |
| experience | `agent_observation` + artifacts `sensor=near_eye` |
| social | `scene_parse` payload に `sensor=near_eye` / `source=koyori` |
| desire | **満たさない**（miss_companion / observe_room を勝手に触らない） |

```powershell
.\scripts\restart-presence-ui.ps1
# PowerShell: シングルクォートで JSON を渡す（\" だと body が壊れる）
curl.exe -X POST http://127.0.0.1:8090/api/v1/autonomous-tick `
  -H "Content-Type: application/json" `
  -d '{"smoke_action":"look_near"}'
```

ゲート用・明示観察は `PRESENCE_NEAR_LOOK_FRESH=1`（`/see`）を既定にする想定。

**次の実装スライス:** ✅ speak / miss_companion 在席ゲート（near fresh struct present → far 救済 · fail-closed）。
やらない当面: 自律の定常 `look_near`、会話「見て」近目既定、ゲート自動 remember、chat TTS / remind へのゲート拡張。

### Phase 4 — フロントエンド UI（任意）

- koyori 本体: キオスク → presence-ui `:8090`（内部で claude-code-webui `:8080` にプロキシ）
- 常時 GStreamer プレビュー（別途）で AE 安定 + 見た目の「目」

---

## 遠目 vs 近目（使い分け）

| 状況 | 使う目 |
|------|--------|
| 部屋の様子・「見て」デフォ・在席救済 | `wifi-cam-mcp` / 遠目 |
| キオスク前在席ゲート · 明示の机/手元 | koyori near（ゲートは bool のみ） |
| 記憶に残す観察 | 遠目が主 · near は明示時のみ（`sensor=near_eye`） |

---

## 既知の制限

- `ov5693.yaml` 無し → uncalibrated（暗い・ノイジー）。物理照明が効く
- dmesg の `dummy regulator` / `INT3472 no dependents` が残っても GStreamer では写像確認済み
- リア cam は Go 1 では libcamera 未登録のことが多い → 使わない
- `cam` + ffmpeg はデバッグ用のみ

---

## 関連ファイル

- [`scripts/koyori-capture.sh`](../../scripts/koyori-capture.sh) — 近目 JPEG キャプチャ
- [`scripts/koyori-kiosk/koyori-see-http.py`](../../scripts/koyori-kiosk/koyori-see-http.py) — Phase 1 HTTP
- [`scripts/koyori-kiosk/install-koyori-near-eye.sh`](../../scripts/koyori-kiosk/install-koyori-near-eye.sh) — install
- [`wifi-cam-mcp`](../../wifi-cam-mcp/) — 遠目 + vision describe 参考実装
- [`CLAUDE.md`](../../CLAUDE.md) — MCP・Heartbeat 全体
