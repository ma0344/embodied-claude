# Temporal anchor benchmark (OL2-temporal)

Japanese relative date resolution for ma-home utility LLM (`qwen2.5-3b-instruct`).

## Run

```powershell
cd presence-ui
$env:PRESENCE_LLM_UTILITY_MODEL = "qwen2.5-3b-instruct"
uv run python ../benchmarks/temporal_anchor/run_suite.py
uv run python ../benchmarks/temporal_anchor/run_suite.py --llm
```

Rules-only checks OL1b/OL1c and OL2 confirmation paths. `--ja-timex` prints extractor spans (Python 3.12 + `pip install ja-timex`). `--llm` scores utility model on harder fixtures.

LM Studio must be running with the utility model loaded. Token: `%USERPROFILE%\.config\embodied-claude\lmstudio.token`.
