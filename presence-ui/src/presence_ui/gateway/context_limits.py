"""Gateway context size limits and tier policy for native chat injection.

ma-home (2026-06): LM Studio context ~87k — lite caps were raised from the 8192-era
1200/2500 defaults. Override via ``presence-ui.local.env`` or process env.

Tier policy (``lite=True`` Room / native chat):

- **Tier 0 — never truncated**: ``[Must include]``, ``[Must avoid]``, ``[Social move]``,
  ``[Action]`` (see ``truncate_lite_turn_delta``).
- **Tier 1 — pin top of compact block**: ``[schedule_facts]``, top ``[relevant_memories]``
  (compose ``_compact_block``).
- **Tier 2 — compose body**: interaction summary, gists, desires, response contract.
- **Tier 3 — trim first when over budget**: ``session_history``, ``[stm_recent]``,
  ``recent_experiences`` (long tail inside ``[Social context]``).
"""

from __future__ import annotations

import os

# Raised from 1200 / 2500 / 6000 (8192 ctx era) — see README + backlog MEM-8b-lite.
_DEFAULT_LITE_COMPOSE = 8000
_DEFAULT_LITE_APPEND = 12000
_DEFAULT_FULL_COMPOSE = 10000
_DEFAULT_ENRICH = 12000
_DEFAULT_LITE_STM = 2500


def _int_env(name: str, default: int, *, minimum: int = 200) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


def lite_compose_max_chars() -> int:
    """Max chars for orchestrator ``compact_prompt_block`` in native chat (lite)."""
    return _int_env("PRESENCE_LITE_COMPOSE_MAX_CHARS", _DEFAULT_LITE_COMPOSE)


def lite_append_max_chars() -> int:
    """Max chars for per-turn ``gateway_turn_context`` in native chat (lite)."""
    return _int_env("PRESENCE_LITE_APPEND_MAX_CHARS", _DEFAULT_LITE_APPEND)


def full_compose_max_chars() -> int:
    """Max chars for compose when ``lite=False`` (heartbeat, status, etc.)."""
    return _int_env("PRESENCE_COMPOSE_MAX_CHARS", _DEFAULT_FULL_COMPOSE)


def enrich_max_chars() -> int:
    """Max chars after somatic + STM append onto ``compact_prompt_block``."""
    return _int_env("PRESENCE_ENRICH_MAX_CHARS", _DEFAULT_ENRICH)


def lite_stm_max_chars() -> int | None:
    """Optional cap on ``[stm_recent]`` in lite chat; ``0`` disables the cap."""
    raw = os.getenv("PRESENCE_LITE_STM_MAX_CHARS", str(_DEFAULT_LITE_STM)).strip()
    if not raw or raw == "0":
        return None
    try:
        value = int(raw)
        return value if value > 0 else None
    except ValueError:
        return _DEFAULT_LITE_STM
