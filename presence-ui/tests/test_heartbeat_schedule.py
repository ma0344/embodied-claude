"""Tests for BIO pulse scheduling."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from interaction_orchestrator_mcp.schemas import InteractionContext, ResponseContract

from presence_ui.heartbeat.pulse_state import AgentPulseState, load_pulse_state, save_pulse_state
from presence_ui.heartbeat.schedule import (
    apply_pulse_schedule,
    compute_next_pulse,
    seconds_until_wake,
    should_run_consolidate_now,
    should_run_dream_now,
)


def _ctx(*, dominant: str | None = None) -> InteractionContext:
    return InteractionContext(
        ts="2026-06-10T12:00:00+00:00",
        local_time="2026-06-10T21:00:00+09:00",
        timezone="Asia/Tokyo",
        agent_state={
            "ts": "2026-06-10T12:00:00+00:00",
            "desires": {},
            "discomforts": {},
            "dominant_desire": dominant,
            "recent_experiences": [],
            "active_arcs": [],
            "private_reflections": 0,
            "interpretation_shifts": 0,
        },
        response_contract=ResponseContract(),
        prompt_summary="test",
        compact_prompt_block="[test]",
    )


def test_compute_next_pulse_chat_shorter_than_autonomous() -> None:
    chat = compute_next_pulse(channel="chat", plan_move="answer_directly", ctx=_ctx())
    auto = compute_next_pulse(channel="autonomous", plan_move="act_autonomously", ctx=_ctx())
    chat_wake = datetime.fromisoformat(chat.next_wake_at)
    auto_wake = datetime.fromisoformat(auto.next_wake_at)
    assert chat_wake < auto_wake


def test_quiet_inward_action_skips_long_defer() -> None:
    tz = ZoneInfo("Asia/Tokyo")
    # 03:00 JST — outward action would defer toward 07:30
    now = datetime(2026, 6, 18, 3, 0, 0, tzinfo=tz)
    with patch("presence_ui.heartbeat.schedule.datetime") as mock_dt:
        mock_dt.now.return_value = now
        outward = compute_next_pulse(
            channel="autonomous",
            plan_move="act_autonomously",
            action="camera_look_outside",
            ctx=_ctx(dominant="look_outside"),
        )
        inward = compute_next_pulse(
            channel="autonomous",
            plan_move="act_autonomously",
            action="think_or_discuss_topic",
            ctx=_ctx(dominant="cognitive_load"),
        )
    outward_wake = datetime.fromisoformat(outward.next_wake_at)
    inward_wake = datetime.fromisoformat(inward.next_wake_at)
    assert "quiet_hours" in outward.reason
    assert outward_wake.hour >= 7
    assert "quiet_inward" in inward.reason
    assert (inward_wake - now).total_seconds() <= 3600


def test_apply_pulse_schedule_persists(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "agent_pulse.json"
    monkeypatch.setenv("PRESENCE_AGENT_PULSE_PATH", str(path))
    state = apply_pulse_schedule(channel="chat", action="agent_response", reason_suffix="hi")
    assert path.is_file()
    loaded = load_pulse_state()
    assert loaded is not None
    assert loaded.next_wake_at == state.next_wake_at
    assert "after_chat" in loaded.reason


def test_seconds_until_wake_zero_when_due(tmp_path: Path, monkeypatch) -> None:
    tz = ZoneInfo("Asia/Tokyo")
    past = datetime.now(tz).isoformat()
    monkeypatch.setenv("PRESENCE_AGENT_PULSE_PATH", str(tmp_path / "pulse.json"))
    save_pulse_state(AgentPulseState(next_wake_at=past, reason="test"))
    assert seconds_until_wake() == 0.0


def test_should_run_consolidate_now_respects_recent_mark(tmp_path: Path, monkeypatch) -> None:
    tz = ZoneInfo("Asia/Tokyo")
    now = datetime.now(tz).replace(hour=3, minute=0, second=0, microsecond=0)
    path = tmp_path / "pulse.json"
    monkeypatch.setenv("PRESENCE_AGENT_PULSE_PATH", str(path))
    save_pulse_state(
        AgentPulseState(
            next_wake_at=now.isoformat(),
            reason="x",
            last_consolidate_at=now.isoformat(),
        )
    )
    with patch("presence_ui.heartbeat.schedule.datetime") as mock_dt:
        mock_dt.now.return_value = now
        assert should_run_consolidate_now() is False


def test_should_run_dream_now_respects_recent_mark(tmp_path: Path, monkeypatch) -> None:
    tz = ZoneInfo("Asia/Tokyo")
    now = datetime.now(tz).replace(hour=3, minute=0, second=0, microsecond=0)
    path = tmp_path / "pulse.json"
    monkeypatch.setenv("PRESENCE_AGENT_PULSE_PATH", str(path))
    save_pulse_state(
        AgentPulseState(
            next_wake_at=now.isoformat(),
            reason="x",
            last_dream_at=now.isoformat(),
        )
    )
    with patch("presence_ui.heartbeat.schedule.datetime") as mock_dt:
        mock_dt.now.return_value = now
        assert should_run_dream_now() is False


def test_pulse_state_roundtrip(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "agent_pulse.json"
    monkeypatch.setenv("PRESENCE_AGENT_PULSE_PATH", str(path))
    original = AgentPulseState(
        next_wake_at="2026-06-17T10:00:00+09:00",
        reason="chat; after_chat",
        last_action="agent_response",
        channel="chat",
    )
    save_pulse_state(original)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["reason"] == "chat; after_chat"
    loaded = load_pulse_state()
    assert loaded is not None
    assert loaded.last_action == "agent_response"
