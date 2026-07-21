"""Brief S0 reasoning flag + local.env persistence."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from presence_ui.gateway.brief_s0_reasoning import (
    ENV_KEY,
    brief_s0_reasoning_enabled,
    reasoning_effort_for_openai,
    set_brief_s0_reasoning,
    upsert_local_env_key,
)
from presence_ui.gateway.gw_silent import run_classifier_turn


def test_brief_s0_reasoning_default_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_KEY, raising=False)
    assert brief_s0_reasoning_enabled() is True


def test_brief_s0_reasoning_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_KEY, "0")
    assert brief_s0_reasoning_enabled() is False


def test_reasoning_effort_mapping() -> None:
    assert reasoning_effort_for_openai(True) == "medium"
    assert reasoning_effort_for_openai(False) == "none"


def test_upsert_local_env_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "presence-ui.local.env"
    monkeypatch.setattr(
        "presence_ui.gateway.brief_s0_reasoning.local_env_path",
        lambda: path,
    )
    upsert_local_env_key(ENV_KEY, "1")
    assert f"{ENV_KEY}=1" in path.read_text(encoding="utf-8")
    upsert_local_env_key(ENV_KEY, "0")
    text = path.read_text(encoding="utf-8")
    assert f"{ENV_KEY}=0" in text
    assert text.count(ENV_KEY) == 1


def test_set_brief_s0_reasoning_updates_environ(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "presence-ui.local.env"
    monkeypatch.setattr(
        "presence_ui.gateway.brief_s0_reasoning.local_env_path",
        lambda: path,
    )
    monkeypatch.delenv(ENV_KEY, raising=False)
    set_brief_s0_reasoning(False)
    assert os_environ_is_off(monkeypatch)
    assert brief_s0_reasoning_enabled() is False
    set_brief_s0_reasoning(True)
    assert brief_s0_reasoning_enabled() is True


def os_environ_is_off(monkeypatch: pytest.MonkeyPatch) -> bool:
    import os

    return os.environ.get(ENV_KEY) == "0"


def test_run_classifier_turn_reasoning_effort_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    def fake_post(_self, url, *, json, headers):
        captured["json"] = json
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {
            "choices": [{"message": {"content": '{"spans":[]}'}}],
        }
        return response

    with (
        patch(
            "presence_ui.gateway.gw_silent.lm_studio_available",
            return_value=True,
        ),
        patch("httpx.Client.post", fake_post),
    ):
        run_classifier_turn(
            system="sys",
            user="hi",
            reasoning=True,
            log_label="test reasoning on",
        )
    assert captured["json"]["reasoning_effort"] == "medium"


def test_run_classifier_turn_reasoning_omitted_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    def fake_post(_self, url, *, json, headers):
        captured["json"] = json
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {
            "choices": [{"message": {"content": "{}"}},],
        }
        return response

    with (
        patch(
            "presence_ui.gateway.gw_silent.lm_studio_available",
            return_value=True,
        ),
        patch("httpx.Client.post", fake_post),
    ):
        run_classifier_turn(system="sys", user="hi", log_label="test no reasoning")
    assert "reasoning_effort" not in captured["json"]
