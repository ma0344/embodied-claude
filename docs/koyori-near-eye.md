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

## 実装ロードマップ（これから作る部分）

### Phase 1 — koyori 上で JPEG を公開

koyori が **最新1枚** を保持し、HTTP で返す。

```
koyori-capture → /var/lib/koyori/latest.jpg
       ↑
systemd timer / path unit（例: 30s ごと、または on-demand）
       ↓
軽量 HTTP（例: Python http.server ラッパー、caddy、nginx）
  GET http://koyori.local:8765/latest.jpg
  GET http://koyori.local:8765/see        → capture してから返す（同期）
```

配置案:

- `/var/lib/koyori/latest.jpg` — 直近キャプチャ
- `/etc/systemd/system/koyori-capture.timer` — 定期更新（暗所なら interval 長め）
- `/usr/local/bin/koyori-see-http` — `see` 要求時に capture + 返却

### Phase 2 — ma-home から取得

**推奨:** ma-home 上の新 MCP（または `wifi-cam-mcp` 拡張）が koyori HTTP を pull。

環境変数例:

```json
"near-cam": {
  "env": {
    "KOYORI_CAM_URL": "http://koyori.local:8765",
    "KOYORI_VISION_DESCRIBE": "true",
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:1234"
  }
}
```

ツール案:

| ツール | 動作 |
|--------|------|
| `see_near` | `GET /latest.jpg` または `/see` → LM Studio vision → テキスト |
| （任意）`near_cam_info` | 解像度・最終更新時刻 |

`wifi-cam-mcp` の `_describe_image_via_lm_studio` と同じ OpenAI `/v1/chat/completions` パターンを流用できる。

### Phase 3 — Claude Code / こよりの行動

- スラッシュコマンド `/see-near`（`allowed-tools`: `mcp__near-cam__see_near`）
- Heartbeat: キオスク前に人がいるとき近目、部屋全体は Tapo `/see`
- `memory-mcp`: `save_visual_memory` に `camera_position=near` / `source=koyori` を付与
- `sociality`: scene parse に `sensor=near_eye` を区別

### Phase 4 — フロントエンド UI（任意）

- koyori 本体: Chromium キオスク → claude-code-webui（ma-home 経由）
- 常時 GStreamer プレビュー（別途）で AE 安定 + 見た目の「目」

---

## 遠目 vs 近目（使い分け）

| 状況 | 使う目 |
|------|--------|
| 部屋の様子・PTZ | `wifi-cam-mcp` see |
| キオスク前の顔・手元・画面越し | koyori near `see_near` |
| 記憶 | `camera_position` / metadata で区別 |

---

## 既知の制限

- `ov5693.yaml` 無し → uncalibrated（暗い・ノイジー）。物理照明が効く
- dmesg の `dummy regulator` / `INT3472 no dependents` が残っても GStreamer では写像確認済み
- リア cam は Go 1 では libcamera 未登録のことが多い → 使わない
- `cam` + ffmpeg はデバッグ用のみ

---

## 関連ファイル

- [`scripts/koyori-capture.sh`](../scripts/koyori-capture.sh) — 近目 JPEG キャプチャ
- [`wifi-cam-mcp`](../wifi-cam-mcp/) — 遠目 + vision describe 参考実装
- [`CLAUDE.md`](../CLAUDE.md) — MCP・Heartbeat 全体
