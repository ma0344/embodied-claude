# Irodori TTS — Python API 参考（ma-home）

**地位**: Gradio 実験 UI（`:7861`）の API ダンプ + ma-home（こより本番 `:8088`）の配線メモ  
**関連**: [backlog-ma-home.md](./backlog-ma-home.md) § Irodori TTS · [ops/irodori-profile.toml.example](./ops/irodori-profile.toml.example) · [ops/scripts-reference.md](./ops/scripts-reference.md) · [architecture/cognitive-layers.md](./architecture/cognitive-layers.md)

---

## 2 つの API（混同注意）

| 用途 | ポート | クライアント | 正本 |
|------|--------|-------------|------|
| **パラメータ試し・Gradio UI** | `:7861` | `gradio_client` | 本 doc [Appendix](#appendix-gradio-client-api-7861) |
| **こより本番 TTS** | `:8088` | `tts-mcp` → `POST /v1/audio/speech` | [Irodori-TTS-Server README](https://github.com/Aratako/Irodori-TTS-Server) |

本番は **OpenAI 互換 API** のみ。Gradio の `/_run_generation` 等は本番サーバには無い。

---

## 本番 API（`:8088`）— こより配線

### リクエスト例

```python
import json
import urllib.request

body = {
    "model": "irodori-tts",
    "input": "まー、おはよう😊 今日もええ天気やな。",
    "voice": "koyori",
    "response_format": "wav",
    "irodori": {
        "num_steps": 24,
        "seed": 8787384312565159089,
        "cfg_scale_text": 3.0,
        "cfg_scale_caption": 10.0,
        "cfg_scale_speaker": 2.0,
        "caption": "落ち着いた関西弁、少し早口。",
    },
}
req = urllib.request.Request(
    "http://127.0.0.1:8088/v1/audio/speech",
    data=json.dumps(body).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
wav_bytes = urllib.request.urlopen(req, timeout=120).read()
```

### Gradio ↔ 本番の対応

| Gradio (`/_run_generation`) | 本番 (`/v1/audio/speech`) |
|------------------------------|---------------------------|
| `text` | `input` |
| `caption` | `irodori.caption` |
| `ref_wav` | `voice: "koyori"` → `Irodori-TTS-Server/voices/koyori.wav` |
| `num_steps`, `seed_raw`, `cfg_scale_*` | `irodori.*` |
| `checkpoint` | `Irodori-TTS-Server/.env` の `IRODORI_HF_CHECKPOINT` / `IRODORI_CHECKPOINT` |

### ma-home の設定ファイル

| 内容 | 場所 |
|------|------|
| 接続・エンジン選択 | `tts-mcp/.env` — `IRODORI_URL`, `TTS_DEFAULT_ENGINE=irodori` |
| 合成レシピ（seed / cfg / caption） | `%USERPROFILE%\.config\embodied-claude\irodori-profile.toml` |
| チェックポイント・preload | `Irodori-TTS-Server/.env` |
| 参照声 WAV | `Irodori-TTS-Server/voices/koyori.wav` |

profile 変更 → `.\scripts\restart-presence-ui.ps1`  
モデル切替 → `.\scripts\restart-irodori-tts-500m.ps1` / `.\scripts\restart-irodori-tts-600m.ps1`

---

## モデル（500M / 600M）

| チェックポイント | caption | 参照声 + caption + emoji | 切替 |
|------------------|---------|--------------------------|------|
| **500M-v3 base** | 無視 | 参照声クローンのみ | `restart-irodori-tts-500m.ps1` |
| **600M-v3-VoiceDesign** | 有効 | 3 分岐（text + ref + caption） | `restart-irodori-tts-600m.ps1`（`irodori-tts` upgrade 込み） |

600M 初回切替で `use_speaker_condition` エラーが出たら:

```powershell
cd C:\Users\ma\src\Irodori-TTS-Server
uv sync --extra cu128 --upgrade-package irodori-tts
```

---

## `text` / `caption` / emoji の役割

| フィールド | 役割 | 例 |
|-----------|------|-----|
| **`caption`**（profile 既定） | ベースの話し方・声色 | 「落ち着いた関西弁、少し早口。」 |
| **`input` / `text` 内の emoji** | その発話の瞬間的な感情・効果音 | 「うーん🤔 それちゃう気するわ😊」 |

- emoji は **caption ではなく発話テキストに埋め込む**
- **同じ emoji を繰り返すと強調**（公式仕様）
- 効果は文脈依存で **100% 安定しない**（HF も明記）
- 600M VoiceDesign ロード時のみ caption + emoji の組み合わせが本線

### 対応 emoji 一覧

- 600M: [EMOJI_ANNOTATIONS.md（HF）](https://huggingface.co/Aratako/Irodori-TTS-600M-v3-VoiceDesign/blob/main/EMOJI_ANNOTATIONS.md)
- Gradio UI の Emoji Palette と同じセット（`irodori_tts/gradio_emoji_palette.py`）

よく使う例: `😊` 嬉しげ · `🤔` 疑問 · `😮‍💨` 溜息 · `⏩` 早口 · `🤭` くすっ · `😭` 悲しげ · `⏸️` 間

---

## Gateway 経路（案 B 実装済み）

表層の **plain reply** は UI / social.db 用のまま。TTS 直前で `prepare_irodori_tts_line()` が e4b enrich する。

```
表層 generate_surface_reply → reply_plain（UI · JSONL · social.db）
  → deliver_gateway_speak_after_reply(reply_plain)
  → deliver_speak_to_kiosk(reply_plain)
  → synthesize_surface_audio(reply_plain)
       └ prepare_irodori_tts_line → POST :8088 input=tts_line

direct_actions → speak_text(reply_plain)  # 内部でも prepare 経由
  + irodori-profile.toml caption（毎回付与）
```

コード: `gateway/irodori_emoji_enrich.py` · `services/tts.py` · `services/tts_surface.py` · `gateway_speak.py` · `kiosk_say.py`

| 変数 | 既定 | 意味 |
|------|------|------|
| `PRESENCE_IRODORI_EMOJI_ENRICH` | `1` | `0` で enrich オフ |
| `PRESENCE_IRODORI_EMOJI_MAX_TOKENS` | `256` | e4b 応答上限 |
| `PRESENCE_CLASSIFIER_MODEL` | `google/gemma-4-e4b-qat` | enrich も classifier 経由 |

- **Stage 1**（ルーティング）: 関係ない
- **Stage 2**（e4b 構造化変換）: `reply_plain` → `{ "tts_input": "..." }` · allowlist 外 emoji は sanitize で除去
- e4b 失敗時: plain のまま TTS
- 表層 SOUL に emoji 指示は **不要**

### IBF gateway speak

`user_intent.py` の `[Action]` は読み上げタイミングのみ。emoji enrich は TTS 層で自動。

---

## Gradio 実験（`:7861`）— koyori 向けパラメータ

`Irodori-TTS` リポで VoiceDesign Gradio を起動したときの参考値（profile.toml と揃える）:

```python
ref_wav = handle_file(r"C:\Users\ma\src\Irodori-TTS-Server\voices\koyori.wav")
text = "まー、おはよう😊 今日もええ天気やな。"
caption = "落ち着いた関西弁、少し早口。"
num_steps = 24
cfg_scale_text = 3
cfg_scale_caption = 10
cfg_scale_speaker = 2
```

Gradio で試した値 → `irodori-profile.toml` / 本番 `:8088` に写す。

---

## Appendix: Gradio Client API (`:7861`)

以下は Gradio UI の **Use via API** からの自動生成ダンプ（2026-07-10 時点）。UI 更新でパラメータ数が変わることがある。

```bash
pip install gradio_client
```

- 主に使うのは `/_run_generation`（生成結果 `[0]` が Audio）
- `/_on_*` は UI 連動用 — 本番 `:8088` には無い
- ダンプ内の `text` / `caption` が同じ `"Hello!!"` になっているのは placeholder。実用では分ける

**API Endpoints: 6**

1. Install the Python client [docs](https://www.gradio.app/guides/getting-started-with-the-python-client) if you don't already have it installed.

2. Find the API endpoint below corresponding to your desired function in the app. Copy the code snippet, replacing the placeholder values with your own input data.

### API Name: /_run_generation


```python
from gradio_client import Client, handle_file

client = Client("http://127.0.0.1:7861/")
result = client.predict(
	checkpoint="Aratako/Irodori-TTS-600M-v3-VoiceDesign",
	model_device="cuda",
	model_precision="fp32",
	codec_device="cuda",
	codec_precision="fp32",
	text="Hello!!",
	caption="Hello!!",
	ref_wav=handle_file('https://github.com/gradio-app/gradio/raw/main/test/test_files/audio_sample.wav'),
	num_steps=40,
	num_candidates=1,
	seed_raw="",
	seconds_raw="",
	duration_scale=1,
	t_schedule_mode="linear",
	sway_coeff=-1,
	cfg_guidance_mode="independent",
	cfg_scale_text=3,
	cfg_scale_caption=4,
	cfg_scale_speaker=5,
	cfg_scale_raw="",
	cfg_min_t=0.5,
	cfg_max_t=1,
	context_kv_cache=True,
	speaker_kv_scale_raw="",
	max_text_len_raw="",
	max_caption_len_raw="",
	truncation_factor_raw="",
	rescale_k_raw="",
	rescale_sigma_raw="",
	lora_adapter_raw="",
	api_name="/_run_generation"
)
print(result)
```

Accepts 30 parameters:

checkpoint:
- Type: str
- Default: "Aratako/Irodori-TTS-600M-v3-VoiceDesign"
- The input value that is provided in the Model Checkpoint (.pt/.safetensors or HF repo id) Textbox component. 

model_device:
- Type: Literal['cuda', 'cpu']
- Default: "cuda"
- The input value that is provided in the Model Device Dropdown component. 

model_precision:
- Type: Literal['fp32', 'bf16']
- Default: "fp32"
- The input value that is provided in the Model Precision Dropdown component. 

codec_device:
- Type: Literal['cuda', 'cpu']
- Default: "cuda"
- The input value that is provided in the Codec Device Dropdown component. 

codec_precision:
- Type: Literal['fp32', 'bf16']
- Default: "fp32"
- The input value that is provided in the Codec Precision Dropdown component. 

text:
- Type: str
- Required
- The input value that is provided in the Text Textbox component. 

caption:
- Type: str
- Required
- The input value that is provided in the Caption / Style Prompt (optional) Textbox component. 

ref_wav:
- Type: filepath
- Required
- The input value that is provided in the Reference Audio Upload (optional, blank = no-reference mode) Audio component. The FileData class is a subclass of the GradioModel class that represents a file object within a Gradio interface. It is used to store file data and metadata when a file is uploaded.

Attributes:
    path: The server file path where the file is stored.
    url: The normalized server URL pointing to the file.
    size: The size of the file in bytes.
    orig_name: The original filename before upload.
    mime_type: The MIME type of the file.
    is_stream: Indicates whether the file is a stream.
    meta: Additional metadata used internally (should not be changed).

num_steps:
- Type: float
- Default: 40
- The input value that is provided in the Num Steps Slider component. 

num_candidates:
- Type: float
- Default: 1
- The input value that is provided in the Num Candidates Slider component. 

seed_raw:
- Type: str
- Default: ""
- The input value that is provided in the Seed (blank=random) Textbox component. 

seconds_raw:
- Type: str
- Default: ""
- The input value that is provided in the Seconds (blank=auto) Textbox component. 

duration_scale:
- Type: float
- Default: 1
- The input value that is provided in the Duration Scale Slider component. 

t_schedule_mode:
- Type: Literal['linear', 'sway']
- Default: "linear"
- The input value that is provided in the Time Schedule Dropdown component. 

sway_coeff:
- Type: float
- Default: -1
- The input value that is provided in the Sway Coeff Slider component. 

cfg_guidance_mode:
- Type: Literal['independent', 'joint', 'alternating']
- Default: "independent"
- The input value that is provided in the CFG Guidance Mode Dropdown component. 

cfg_scale_text:
- Type: float
- Default: 3
- The input value that is provided in the CFG Scale Text Slider component. 

cfg_scale_caption:
- Type: float
- Default: 4
- The input value that is provided in the CFG Scale Caption Slider component. 

cfg_scale_speaker:
- Type: float
- Default: 5
- The input value that is provided in the CFG Scale Speaker Slider component. 

cfg_scale_raw:
- Type: str
- Default: ""
- The input value that is provided in the CFG Scale Override (optional) Textbox component. 

cfg_min_t:
- Type: float
- Default: 0.5
- The input value that is provided in the CFG Min t Number component. 

cfg_max_t:
- Type: float
- Default: 1
- The input value that is provided in the CFG Max t Number component. 

context_kv_cache:
- Type: bool
- Default: True
- The input value that is provided in the Context KV Cache Checkbox component. 

speaker_kv_scale_raw:
- Type: str
- Default: ""
- The input value that is provided in the Speaker KV Scale (optional) Textbox component. 

max_text_len_raw:
- Type: str
- Default: ""
- The input value that is provided in the Max Text Len (optional) Textbox component. 

max_caption_len_raw:
- Type: str
- Default: ""
- The input value that is provided in the Max Caption Len (optional) Textbox component. 

truncation_factor_raw:
- Type: str
- Default: ""
- The input value that is provided in the Truncation Factor (optional) Textbox component. 

rescale_k_raw:
- Type: str
- Default: ""
- The input value that is provided in the Rescale k (optional) Textbox component. 

rescale_sigma_raw:
- Type: str
- Default: ""
- The input value that is provided in the Rescale sigma (optional) Textbox component. 

lora_adapter_raw:
- Type: str
- Default: ""
- The input value that is provided in the LoRA Adapter Directory (optional) Textbox component. 

Returns tuple of 34 elements:

[0]: - Type: filepath
- The output value that appears in the "Generated Audio 1" Audio component.

[1]: - Type: filepath
- The output value that appears in the "Generated Audio 2" Audio component.

[2]: - Type: filepath
- The output value that appears in the "Generated Audio 3" Audio component.

[3]: - Type: filepath
- The output value that appears in the "Generated Audio 4" Audio component.

[4]: - Type: filepath
- The output value that appears in the "Generated Audio 5" Audio component.

[5]: - Type: filepath
- The output value that appears in the "Generated Audio 6" Audio component.

[6]: - Type: filepath
- The output value that appears in the "Generated Audio 7" Audio component.

[7]: - Type: filepath
- The output value that appears in the "Generated Audio 8" Audio component.

[8]: - Type: filepath
- The output value that appears in the "Generated Audio 9" Audio component.

[9]: - Type: filepath
- The output value that appears in the "Generated Audio 10" Audio component.

[10]: - Type: filepath
- The output value that appears in the "Generated Audio 11" Audio component.

[11]: - Type: filepath
- The output value that appears in the "Generated Audio 12" Audio component.

[12]: - Type: filepath
- The output value that appears in the "Generated Audio 13" Audio component.

[13]: - Type: filepath
- The output value that appears in the "Generated Audio 14" Audio component.

[14]: - Type: filepath
- The output value that appears in the "Generated Audio 15" Audio component.

[15]: - Type: filepath
- The output value that appears in the "Generated Audio 16" Audio component.

[16]: - Type: filepath
- The output value that appears in the "Generated Audio 17" Audio component.

[17]: - Type: filepath
- The output value that appears in the "Generated Audio 18" Audio component.

[18]: - Type: filepath
- The output value that appears in the "Generated Audio 19" Audio component.

[19]: - Type: filepath
- The output value that appears in the "Generated Audio 20" Audio component.

[20]: - Type: filepath
- The output value that appears in the "Generated Audio 21" Audio component.

[21]: - Type: filepath
- The output value that appears in the "Generated Audio 22" Audio component.

[22]: - Type: filepath
- The output value that appears in the "Generated Audio 23" Audio component.

[23]: - Type: filepath
- The output value that appears in the "Generated Audio 24" Audio component.

[24]: - Type: filepath
- The output value that appears in the "Generated Audio 25" Audio component.

[25]: - Type: filepath
- The output value that appears in the "Generated Audio 26" Audio component.

[26]: - Type: filepath
- The output value that appears in the "Generated Audio 27" Audio component.

[27]: - Type: filepath
- The output value that appears in the "Generated Audio 28" Audio component.

[28]: - Type: filepath
- The output value that appears in the "Generated Audio 29" Audio component.

[29]: - Type: filepath
- The output value that appears in the "Generated Audio 30" Audio component.

[30]: - Type: filepath
- The output value that appears in the "Generated Audio 31" Audio component.

[31]: - Type: filepath
- The output value that appears in the "Generated Audio 32" Audio component.

[32]: - Type: str
- The output value that appears in the "Run Log" Textbox component.

[33]: - Type: str
- The output value that appears in the "Timing" Textbox component.



### API Name: /_on_model_device_change


```python
from gradio_client import Client

client = Client("http://127.0.0.1:7861/")
result = client.predict(
	device="cuda",
	api_name="/_on_model_device_change"
)
print(result)
```

Accepts 1 parameter:

device:
- Type: Literal['cuda', 'cpu']
- Default: "cuda"
- The input value that is provided in the Model Device Dropdown component. 

Returns 1 element:

- Type: Literal['fp32', 'bf16']
- The output value that appears in the "Model Precision" Dropdown component.



### API Name: /_on_codec_device_change


```python
from gradio_client import Client

client = Client("http://127.0.0.1:7861/")
result = client.predict(
	device="cuda",
	api_name="/_on_codec_device_change"
)
print(result)
```

Accepts 1 parameter:

device:
- Type: Literal['cuda', 'cpu']
- Default: "cuda"
- The input value that is provided in the Codec Device Dropdown component. 

Returns 1 element:

- Type: Literal['fp32', 'bf16']
- The output value that appears in the "Codec Precision" Dropdown component.



### API Name: /_on_t_schedule_mode_change


```python
from gradio_client import Client

client = Client("http://127.0.0.1:7861/")
result = client.predict(
	mode="linear",
	api_name="/_on_t_schedule_mode_change"
)
print(result)
```

Accepts 1 parameter:

mode:
- Type: Literal['linear', 'sway']
- Default: "linear"
- The input value that is provided in the Time Schedule Dropdown component. 

Returns 1 element:

- Type: float
- The output value that appears in the "Sway Coeff" Slider component.



### API Name: /_describe_runtime


```python
from gradio_client import Client

client = Client("http://127.0.0.1:7861/")
result = client.predict(
	checkpoint="Aratako/Irodori-TTS-600M-v3-VoiceDesign",
	model_device="cuda",
	model_precision="fp32",
	codec_device="cuda",
	codec_precision="fp32",
	api_name="/_describe_runtime"
)
print(result)
```

Accepts 5 parameters:

checkpoint:
- Type: str
- Default: "Aratako/Irodori-TTS-600M-v3-VoiceDesign"
- The input value that is provided in the Model Checkpoint (.pt/.safetensors or HF repo id) Textbox component. 

model_device:
- Type: Literal['cuda', 'cpu']
- Default: "cuda"
- The input value that is provided in the Model Device Dropdown component. 

model_precision:
- Type: Literal['fp32', 'bf16']
- Default: "fp32"
- The input value that is provided in the Model Precision Dropdown component. 

codec_device:
- Type: Literal['cuda', 'cpu']
- Default: "cuda"
- The input value that is provided in the Codec Device Dropdown component. 

codec_precision:
- Type: Literal['fp32', 'bf16']
- Default: "fp32"
- The input value that is provided in the Codec Precision Dropdown component. 

Returns 1 element:

- Type: str
- The output value that appears in the "Model Status" Textbox component.



### API Name: /_clear_runtime_cache


```python
from gradio_client import Client

client = Client("http://127.0.0.1:7861/")
result = client.predict(
	api_name="/_clear_runtime_cache"
)
print(result)
```

Accepts 0 parameters:



Returns 1 element:

- Type: str
- The output value that appears in the "Model Status" Textbox component.

