# VIS-e4b POC - 2026-06-29 06:05 UTC

- **image**: `C:\tmp\wifi-cam-mcp\capture_20260629_142631.jpg`
- **prompt**: `WIFI_CAM_VISION_PROMPT` → system (33 chars)
- **isolate**: `True` (unload peers + reload each model before describe)

| model | chars | finish | api | corrupt | ok |
|-------|------:|--------|-----|---------|-----|
| `qwen2.5-vl-3b-instruct` | 99 | stop | chat/completions | no | ✅ |
| `google/gemma-4-e4b` | 113 | length | chat/completions | no | ✅ |

## qwen2.5-vl-3b-instruct

```
写真には、椅子に座っている男性がいます。彼はパソコンの前におり、画面を見ています。机の上には複数のデバイスや文書が置かれています。背景には白い扉と木製の家具があり、部屋全体は明るく照らされています。
```

## google/gemma-4-e4b

```
この写真は、オフィスの一角で作業をしている男性を捉えた屋内写真です。

**主要な描写:**

*   **人物:** 写真の中央左寄りに、眼鏡をかけた男性が椅子に座っています。白っぽいTシャツと、紫がかった長ズボン（またはス
```
