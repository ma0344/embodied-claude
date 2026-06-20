"""SOUL.core loading for stable gateway append."""

from __future__ import annotations

import pytest

from presence_ui.services.llm import (
    SOUL_VOICE_ANCHOR,
    build_gateway_stable_append,
    load_soul_core,
)


def test_load_soul_core_from_env(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    core = tmp_path / "core.md"
    core.write_text("うちはこより。関西弁。", encoding="utf-8")
    monkeypatch.setenv("PRESENCE_SOUL_CORE_PATH", str(core))
    assert load_soul_core() == "うちはこより。関西弁。"


def test_build_gateway_stable_append_uses_core_when_present(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = tmp_path / "core.md"
    core.write_text("一人称はうち。", encoding="utf-8")
    monkeypatch.setenv("PRESENCE_SOUL_CORE_PATH", str(core))
    append = build_gateway_stable_append()
    assert "[SOUL core — mandatory for every reply]" in append
    assert "一人称はうち。" in append
    assert SOUL_VOICE_ANCHOR not in append


def test_build_gateway_stable_append_falls_back_to_voice_anchor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "presence_ui.services.llm.load_soul_core",
        lambda **kwargs: "",
    )
    append = build_gateway_stable_append()
    assert SOUL_VOICE_ANCHOR in append
    assert "[SOUL core — mandatory" not in append


def test_build_gateway_stable_append_respects_in_append_flag(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = tmp_path / "core.md"
    core.write_text("core body", encoding="utf-8")
    monkeypatch.setenv("PRESENCE_SOUL_CORE_PATH", str(core))
    monkeypatch.setenv("PRESENCE_SOUL_CORE_IN_APPEND", "0")
    append = build_gateway_stable_append()
    assert SOUL_VOICE_ANCHOR in append
    assert "core body" not in append
