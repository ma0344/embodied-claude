"""LW-7 — reading PAUSE followup_query → bounded web search (opt-in)."""

from __future__ import annotations

import os
from pathlib import Path

from presence_ui.gateway.aozora import ReadingState, load_reading_state, save_reading_state


def lw7_enabled() -> bool:
    """When false (default), pending_followup_query is stored but not consumed."""
    raw = os.getenv("PRESENCE_LW7_ENABLED", "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def pending_followup_query(state: ReadingState) -> str:
    return (state.pending_followup_query or "").strip()[:240]


def should_run_lw7_web_search(state: ReadingState) -> bool:
    return lw7_enabled() and bool(pending_followup_query(state))


def clear_pending_followup(state_path: Path | None = None) -> ReadingState:
    state = load_reading_state(state_path)
    state.pending_followup_query = ""
    save_reading_state(state, state_path)
    return state
