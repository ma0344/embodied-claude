"""Feature flags — surface chat without Claude Code subprocess."""

from __future__ import annotations

import os


def surface_use_claude() -> bool:
    """Legacy: force Claude Code CLI for surface replies."""
    raw = os.environ.get("PRESENCE_SURFACE_USE_CLAUDE", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def surface_direct_enabled() -> bool:
    """When True (default), native chat uses LM Studio direct instead of Claude Code."""
    if surface_use_claude():
        return False
    raw = os.environ.get("PRESENCE_SURFACE_DIRECT", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def use_surface_direct_path() -> bool:
    return surface_direct_enabled()


def camera_vision_via_surface_enabled() -> bool:
    """Conversational see — JPEG direct to surface 12b multimodal (no vision_prefetch caption)."""
    return surface_direct_enabled()


def compose_omit_session_transcript_in_compact(session_key: str | None) -> bool:
    """Whether compose should omit full session transcript (Claude Code JSONL resume path).

    Surface Direct has no CC resume KV — keep ``claude_session_resume=False`` so
    ``compact_prompt_block`` includes ``[recent_room_context]`` for injection debug
    and models that read gateway_turn_context only.
    """
    if not session_key:
        return False
    return not use_surface_direct_path()
