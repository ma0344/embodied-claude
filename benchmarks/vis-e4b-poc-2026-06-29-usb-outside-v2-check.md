# VIS-e4b POC - 2026-06-29 06:18 UTC

- **image**: `C:\Users\ma\.claude\captures\usb\usb_20260629_141812.jpg`
- **prompt**: `WIFI_CAM_VISION_PROMPT` → system (73 chars)
- **prompt preview**: `この写真の見えているものを具体的に日本語で書いてください。人物・姿勢・家具・明るさ・窓やモニタの有無。推測や見えないことは書かない。5〜8文程度。`
- **isolate**: `True` (unload peers + reload each model before describe)

| model | chars | finish | api | corrupt | ok |
|-------|------:|--------|-----|---------|-----|
| `qwen2.5-vl-3b-instruct` | 128 | stop | chat/completions | no | ✅ |
| `google/gemma-4-e4b` | 52 | length | chat/completions | no | ✅ |

## qwen2.5-vl-3b-instruct

```
部屋には、ベージュ色のカーテンで覆われた大きな窓があります。窓からは緑豊かな庭が見えます。窓際には、赤いソファと木製の椅子が配置されています。壁は薄いベージュ色で、天井には小さな照明器具が設置されています。部屋全体は明るく、快適な雰囲気を醸し出しています。
```

## google/gemma-4-e4b

```
この画像は、明るい日差しが差し込む屋内空間を捉えたものです。壁面の大半は窓となっており、そこには光を通す
```
