"""Tests for LW-7 followup_query → web_search prep."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from presence_ui.gateway import direct_actions, lw7
from presence_ui.gateway.aozora import ReadingState, load_reading_state, save_reading_state


def test_lw7_enabled_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRESENCE_LW7_ENABLED", raising=False)
    assert lw7.lw7_enabled() is False


def test_should_run_lw7_requires_flag_and_query(monkeypatch: pytest.MonkeyPatch) -> None:
    state = ReadingState(pending_followup_query="下人とは誰")
    monkeypatch.delenv("PRESENCE_LW7_ENABLED", raising=False)
    assert lw7.should_run_lw7_web_search(state) is False

    monkeypatch.setenv("PRESENCE_LW7_ENABLED", "1")
    assert lw7.should_run_lw7_web_search(state) is True

    state.pending_followup_query = ""
    assert lw7.should_run_lw7_web_search(state) is False


def test_clear_pending_followup(tmp_path: Path) -> None:
    path = tmp_path / "aozora_read_state.json"
    state = ReadingState(pending_followup_query="羅生門 下人")
    save_reading_state(state, path)
    cleared = lw7.clear_pending_followup(path)
    assert cleared.pending_followup_query == ""
    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert reloaded.get("pending_followup_query") == ""


@pytest.mark.asyncio
async def test_inward_tick_runs_lw7_web_search_when_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_LW7_ENABLED", "1")
    state_path = tmp_path / "aozora_read_state.json"
    save_reading_state(
        ReadingState(phase="read", pending_followup_query="下人とは誰"),
        state_path,
    )

    stores = MagicMock()
    ctx = MagicMock()
    ctx.agent_state.dominant_desire = "literary_wander"
    ctx.commitments_due = []
    ctx.open_loops = []
    plan = MagicMock()
    plan.primary_move = "act_autonomously"
    plan.initiative.allowed_actions = [
        "read_aozora_passage",
        "reflect_on_aozora_passage",
        "web_search",
    ]
    plan.followup_action = {}

    web_outcome = direct_actions.DirectActionOutcome(
        ok=True,
        action="web_search",
        summary="下人は…",
        detail="下人とは誰",
        desire_satisfied="browse_curiosity",
    )

    with (
        patch(
            "presence_ui.gateway.direct_actions.inward_autonomous_window",
            return_value=True,
        ),
        patch(
            "presence_ui.gateway.direct_actions.load_reading_state",
            side_effect=lambda path=None: load_reading_state(state_path),
        ),
        patch(
            "presence_ui.gateway.direct_actions.clear_pending_followup",
            side_effect=lambda path=None: lw7.clear_pending_followup(state_path),
        ),
        patch(
            "presence_ui.gateway.direct_actions.web_search_direct",
            new_callable=AsyncMock,
            return_value=web_outcome,
        ) as web_mock,
        patch(
            "presence_ui.gateway.direct_actions._finalize_autonomous_outcome",
            new_callable=AsyncMock,
            side_effect=lambda *args, **kwargs: kwargs.get("outcome") or args[4],
        ),
    ):
        outcome = await direct_actions.execute_autonomous_plan(
            stores,
            person_id="ma",
            ctx=ctx,
            plan=plan,
        )

    web_mock.assert_awaited_once()
    assert web_mock.await_args.kwargs["query"] == "下人とは誰"
    assert web_mock.await_args.kwargs["source"] == "lw7"
    assert outcome.action == "web_search"
    reloaded = json.loads(state_path.read_text(encoding="utf-8"))
    assert reloaded.get("pending_followup_query") == ""
