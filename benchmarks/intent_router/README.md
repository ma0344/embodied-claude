# Intent Router Benchmark (IBF-7 / C12)

Offline harness comparing **rule-based** `resolve_user_intent` labels vs an optional **LM Studio JSON classifier** on fixed Japanese utterances.

## Running

```bash
# Rules only (CI-safe; explicit fixtures must match 100%).
uv run --directory presence-ui python ../benchmarks/intent_router/run_suite.py

# Rules + LM Studio diff report.
uv run --directory presence-ui python ../benchmarks/intent_router/run_suite.py --llm

# pytest
uv run --directory presence-ui pytest ../benchmarks/intent_router/test_suite.py -v
```

LM Studio: same env as gateway (`ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN` or `~/.config/embodied-claude/lmstudio.token`).

## Fixture categories

| category | meaning |
|----------|---------|
| `explicit` | Rules must match `expected_labels` (regression) |
| `ambiguous` | Golden label = human intent; rules may differ — LLM experiment target |

## Labels (taxonomy)

`chat`, `speech`, `remember`, `observe_*`, `ptz_*` — see `taxonomy.py`.

Aligned with [intent-bucket-flow.md §5](../docs/intent-bucket-flow.md) buckets + observe/ptz sub-modes.

## Floors

- **Rules / explicit**: 100% (blocks `SUITE FAIL`)
- **LLM / explicit**: soft 50% in pytest (informational until C12 ships)

## ma-home 計測メモ（2026-06-17, Gemma QAT）

`run_suite.py --llm` on ma-home:

| 指標 | 結果 |
|------|------|
| rules / explicit | **13/13 (100%)** |
| llm / explicit | **12/13 (92%)** |
| llm / ambiguous | **3/3 (100%)** |

**唯一の LLM explicit miss**: `01_explicit_say` — expected `['speech']`, got `['chat', 'speech']`.
ルールは正しく、LLM が `chat` を余計に足しただけ。gateway 実装では **body ラベルがあれば `chat` は無視**してよい（C12 採点も superset 許容を検討）。

**ambiguous 3 件**（rules はすべて `chat`）:

| fixture | LLM | 意味 |
|---------|-----|------|
| `デスク周りどう？` | `observe_desk` | ルール gap を LLM が埋めた |
| `ちょっと左` | `ptz_left` | 同上 |
| `上向いて` | `ptz_up` | 同上 |

**C12 への示唆**: 本番は **regex 優先 → rules が `chat` のみ & 短文/曖昧パターンだけ LLM**。明示文はルールのまま（速い・100%）。

## Adding fixtures

Drop `fixtures/NN_name.json`:

```json
{
  "id": "my_case",
  "description": "...",
  "category": "explicit",
  "user_text": "まーのデスク見て",
  "expected_labels": ["observe_desk"]
}
```

## Related

- [intent-bucket-flow.md §7.2](../docs/intent-bucket-flow.md) — LLM fallback design
- [backlog C12](../docs/backlog-ma-home.md) — production router (after IBF-7 data)
