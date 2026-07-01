# Stage1 → loop routing (GW-S2 / OL7)

Stage1 (e4b) classifies each human utterance into a fixed **`utterance_kind`** taxonomy.
Completion **shape** is a separate field `close_shape` (only when `past_completion`).

Gateway does **not** grow verb regex lists for OL close. Regex stays limited to finite,
deterministic tasks (dates, until-times, prompt fences, recall/dismiss filters).

## utterance_kind → downstream

| kind | route | OL5 | OL7 | notes |
|------|-------|-----|-----|-------|
| `future_commitment` | Stage2 open | — | skip | creates open loop + activity_frame |
| `past_completion` | OL5 + OL7 close | try close | eligible | needs Stage1 TRUE (not gateway regex) |
| `past_report` | no loop | skip | skip | narrative only |
| `greeting` | no loop | skip | skip | |
| `correction` | correction | skip | skip | TEMP-C correction path |
| `calendar_read` | GAPI read (ingest) | skip | skip | chat は L0 prefetch（2r-S2 で Stage1 統合） |
| `calendar_write` | GAPI write / 7b | skip | skip | create/update + confirm |
| `calendar_operation` | GAPI write (legacy) | skip | skip | **alias** → normalize to read/write |
| `other` | no loop | skip | skip | |

Defined in `presence_ui/gateway/stage1_kinds.py` (`STAGE1_ROUTES`).

## past_completion + close_shape

| close_shape | meaning | OL7 frame match | unscoped departure close |
|-------------|---------|-----------------|--------------------------|
| `activity_named` | object slot names the activity (お昼寝 終わった) | yes | no |
| `action_only` | action only, no object (終わったよ / してきたよ) | only if utterance names activity | yes, if exactly one departure loop |
| (inferred) | gateway fills from slots when model omits field | same as above | same |

### Contextual wake greeting (Q3a)

When `open_departure_loops` has **exactly one** departure loop and the utterance is a short
wake/return greeting (おはよう / 起きた — no activity name in text), Stage1 may classify
`past_completion` + `action_only` instead of plain `greeting`.

**Permissive framing (POC):** prompts ask whether the utterance is **not wrong** as a completion
signal (`間違いではない`), not whether it is **appropriate** or **natural** in dictionary/time-of-day
sense. This avoids FALSE on e.g. おはよう after 昼寝してくる.

Gateway injects `open_departure_loops` into the Stage1 user task. Safety net:
`promote_contextual_wake_greeting_if_cued()` (finite phrase list, not verb-regex growth).

Morning「おはよう」with no open departure → still `greeting` (no false close).

`is_action_only_close()` in `social_core.activity_frame` gates the unscoped path.
`activity_named` never uses unscoped departure fallback.

## OL7 resolution order (past_completion)

1. **Activity frame match** — `frames_match_completion` on open loops with frames.
   Single hit → immediate close (no LLM).
2. **Unscoped departure** — `action_only` + exactly one `mode=departure` loop → immediate close.
3. **OL7 classifier** — disambiguate multiple departure loops or weak frame match.
4. **Legacy regex fallback** (Stage1 off only) — known return phrases + departure topic patterns in
   `ol7_return_signal.py`; prefer Stage1 + frames when GW-S2 is on.

## Logging (ma-home debug)

After ingest, look for:

- `GW-S2 apply: … kind=past_completion close_shape=action_only …`
- `OL7 frame match` / `OL7 unscoped past_completion` / `OL7 classify:`

## Related

- Runbook: [ol7-morning-close-test.md](../ops/ol7-morning-close-test.md)
- Prompts: `presence_ui/gateway/ol_gate_prompts.py` (Q1–Q7 flow)
- Activity frames: `social_core/activity_frame.py`
