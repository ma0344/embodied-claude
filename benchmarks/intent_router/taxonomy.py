"""IBF-7 / C12 intent label taxonomy — re-exports presence-ui canonical module."""

from presence_ui.gateway.intent_labels import (  # noqa: F401
    ALL_LABELS,
    BODY_LABELS,
    LLM_INTENT_SYSTEM_PROMPT as LLM_SYSTEM_PROMPT,
    normalize_intent_labels,
)
