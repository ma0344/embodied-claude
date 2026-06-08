---
description: "カメラで1枚撮影し、視覚モデルの説明を返す（LM Studio / wifi-cam 向け）"
allowed-tools: ["mcp__wifi-cam__see"]
---

# /see — いま正面を見る

## 必須（ローカル LLM 向け）

1. **MCP ツール `mcp__wifi-cam__see` を1回だけ呼ぶ**
   - Bash / Skill / シェルコマンドとして実行しない（`mcp__wifi-cam__see` はコマンド名ではない）
   - `camera_info` / `Read` / `look_around` は使わない
2. ツール結果の **`=== VISION_CAPTION ===` ブロックの中身だけ**を要約して伝える
3. **`VISION_DESCRIBE_FAILED` のとき**は「画像は撮れたが自動説明に失敗」と伝え、`file_path` を案内する。**デスク・コーヒー等の推測は禁止**
4. `VISION_CAPTION` が無いのに部屋の描写を作らない（それは幻覚）

## 禁止

- `Bash(mcp__wifi-cam__see)` や `uv run` での代替実行
- JPEG を `Read` ツールで開く（LM Studio 経由では API 400 になりやすい）
- ツール結果に無い物体・情景の想像での説明
