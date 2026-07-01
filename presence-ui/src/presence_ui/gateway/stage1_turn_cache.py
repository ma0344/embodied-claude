"""Back-compat re-exports — prefer gateway_turn_cache."""

from presence_ui.gateway.gateway_turn_cache import (  # noqa: F401
    gateway_turn_cache_scope,
    get_or_set_cached_stage1,
    prefetch_window_cache_key,
    stage1_cache_key,
    stage1_turn_cache_scope,
)
