"""Per-turn cache for gateway e4b work — one LLM call per utterance per chat turn."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Callable, TypeVar

if TYPE_CHECKING:
    from presence_ui.gateway.calendar_read_window import PrefetchWindow
    from presence_ui.gateway.ol_gate import OlGateParsed
    from presence_ui.gateway.stage1_context import Stage1DepartureHint

_T = TypeVar("_T")

_cache_var: ContextVar[dict[tuple, object] | None] = ContextVar(
    "gateway_turn_cache",
    default=None,
)


def stage1_cache_key(
    utterance: str,
    open_departure_loops: tuple[Stage1DepartureHint, ...] | list[Stage1DepartureHint] = (),
) -> tuple[str, tuple[tuple[str, str], ...]]:
    text = (utterance or "").strip()
    hints = tuple(
        (str(h.loop_id), str(h.topic))
        for h in (open_departure_loops or ())
    )
    return ("stage1", text, hints)


def prefetch_window_cache_key(
    utterance: str,
    *,
    anchor_iso: str,
    tz_name: str,
    fallback_day_range: tuple[str, ...] | list[str] | None,
) -> tuple:
    text = (utterance or "").strip()
    day_range = tuple(fallback_day_range or ())
    return ("prefetch_window", text, anchor_iso.strip(), tz_name.strip(), day_range)


def calendar_search_cache_key(utterance: str) -> tuple[str, str]:
    return ("calendar_search", (utterance or "").strip())


def doc_intent_cache_key(utterance: str, doc_id: str, gate_reason: str) -> tuple[str, str, str, str]:
    return (
        "doc_intent",
        (utterance or "").strip(),
        (doc_id or "").strip(),
        (gate_reason or "").strip(),
    )


def doc_hon_cache_key(utterance: str) -> tuple[str, str]:
    return ("doc_hon", (utterance or "").strip())


@contextmanager
def gateway_turn_cache_scope():
    """Activate gateway dedup for one chat turn (prefetch + ingest + gates)."""
    token = _cache_var.set({})
    try:
        yield
    finally:
        _cache_var.reset(token)


# Back-compat alias
stage1_turn_cache_scope = gateway_turn_cache_scope


def get_or_set_cached(key: tuple, factory: Callable[[], _T]) -> _T:
    cache = _cache_var.get()
    if cache is None:
        return factory()
    if key not in cache:
        cache[key] = factory()
    return cache[key]  # type: ignore[return-value]


def get_or_set_cached_stage1(
    key: tuple,
    factory: Callable[[], OlGateParsed | None],
) -> OlGateParsed | None:
    return get_or_set_cached(key, factory)


def get_or_set_cached_prefetch_window(
    key: tuple,
    factory: Callable[[], PrefetchWindow],
) -> PrefetchWindow:
    return get_or_set_cached(key, factory)
