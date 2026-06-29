# VIS-e4b POC - 2026-06-29 06:04 UTC

- **image**: `C:\Users\ma\.claude\captures\usb\usb_20260629_141812.jpg`
- **prompt**: `WIFI_CAM_VISION_PROMPT` → system (33 chars)
- **isolate**: `True` (unload peers + reload each model before describe)

| model | chars | finish | api | corrupt | ok |
|-------|------:|--------|-----|---------|-----|
| `qwen2.5-vl-3b-instruct` | 133 | stop | chat/completions | no | ✅ |
| `google/gemma-4-e4b` | 111 | length | chat/completions | no | ✅ |

## qwen2.5-vl-3b-instruct

```
部屋の一角で、ベージュ色のカーテンが開けた窓から外の景色が見えます。窓の外には緑豊かな植物があり、少し曇りがかった空気を感じさせます。室内にはソファと椅子が配置されており、リラックスした雰囲気が漂っています。照明は自然光に頼っており、落ち着いた空間を演出しています。
```

## google/gemma-4-e4b

```
この写真は、室内から庭園を眺めているリビングルームのような空間の様子を写したものです。

**【室内の要素】**
*   手前左側には、茶色系の座り心地の良いアームチェアまたはソファが置かれています。
*   写真の下部右
```
