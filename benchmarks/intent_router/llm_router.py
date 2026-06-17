"""Optional LM Studio JSON intent classifier — re-exports presence-ui canonical module."""

from presence_ui.gateway.llm_intent import (  # noqa: F401
    classify_with_llm,
    lm_studio_available,
)
