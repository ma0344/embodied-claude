# VIS-e4b POC - 2026-06-29 06:19 UTC

- **image**: `\tmp\wifi-cam-mcp\capture_20260629_151903.jpg`
- **prompt**: `WIFI_CAM_VISION_PROMPT` → system (73 chars)
- **prompt preview**: `この写真の見えているものを具体的に日本語で書いてください。人物・姿勢・家具・明るさ・窓やモニタの有無。推測や見えないことは書かない。5〜8文程度。`
- **isolate**: `True` (unload peers + reload each model before describe)

| model | chars | finish | api | corrupt | ok |
|-------|------:|--------|-----|---------|-----|
| `qwen2.5-vl-3b-instruct` | 93 | stop | chat/completions | no | ✅ |
| `google/gemma-4-e4b` | 169 | length | chat/completions | no | ✅ |

## qwen2.5-vl-3b-instruct

```
写真には、椅子に座っている男性がいます。彼はパソコンの前におり、画面を見ています。部屋は明るく、窓やモニタは見えません。机の上には書類や文房具があります。背景には冷蔵庫とドアが見えます。
```

## google/gemma-4-e4b

```
この写真は、屋内のオフィスまたは作業スペースを写したものです。
手前左側には人物が一人座っており、デスクに向かいながらモニターの内容を見ている姿勢です。
机上には広範囲にわたって電子機器が配置されており、複数のモニターが確認できます。特に大きなメインの画面は、何か具体的な映像内容を表示しています。
家具としては、作業用の広い木製デスクと
```
