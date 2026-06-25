"""Context limit defaults (87k ctx ma-home)."""

from __future__ import annotations

from presence_ui.gateway.context_limits import (
    enrich_max_chars,
    full_compose_max_chars,
    lite_append_max_chars,
    lite_compose_max_chars,
    lite_stm_max_chars,
)


def test_lite_defaults_raised_from_8192_era() -> None:
    assert lite_compose_max_chars() >= 8000
    assert lite_append_max_chars() >= 12000
    assert enrich_max_chars() >= 12000
    assert full_compose_max_chars() >= 10000


def test_lite_stm_cap_optional(monkeypatch) -> None:
    monkeypatch.setenv("PRESENCE_LITE_STM_MAX_CHARS", "0")
    assert lite_stm_max_chars() is None
