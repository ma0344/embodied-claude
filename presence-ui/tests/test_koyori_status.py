"""Tests for Koyori status aggregation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from presence_ui.schemas import AgentPulseView, PlanPreviewView
from presence_ui.services.status import (
    _pick_primary_reading,
    _pick_temperature,
    fetch_koyori_status,
)


def test_pick_primary_reading_prefers_cpu() -> None:
    temps = [
        {"name": "GPU Hotspot", "temperature_celsius": 72.0},
        {"name": "CPU Package", "temperature_celsius": 58.0},
    ]
    picked = _pick_primary_reading(temps)
    assert picked is not None
    assert picked["name"] == "CPU Package"


@patch("presence_ui.services.status.get_all_temperatures")
def test_pick_temperature_includes_readings(mock_get: MagicMock) -> None:
    mock_get.return_value = {
        "feeling": "快適やで〜。ちょうどええ感じ！",
        "temperatures": [
            {
                "name": "CPU Package",
                "temperature_celsius": 52.0,
                "source": "windows_hardware_monitor",
            },
            {
                "name": "GPU",
                "temperature_celsius": 48.0,
                "source": "windows_hardware_monitor",
            },
        ],
    }
    view = _pick_temperature()
    assert view.celsius == 52.0
    assert view.source == "CPU Package"
    assert len(view.readings) == 2


@patch("presence_ui.services.status._fetch_autonomous_plan_preview")
@patch("presence_ui.services.status._fetch_agent_pulse")
@patch("presence_ui.services.status.get_stores")
@patch("presence_ui.services.status.load_desire_snapshot")
@patch("presence_ui.services.status.get_all_temperatures")
def test_fetch_koyori_status_includes_pulse_and_plan(
    mock_temps: MagicMock,
    mock_desires: MagicMock,
    mock_get_stores: MagicMock,
    mock_pulse: MagicMock,
    mock_plan: MagicMock,
) -> None:
    mock_temps.return_value = {"temperatures": [], "feeling": "unknown"}
    mock_desires.return_value = {
        "desires": {"observe_room": 0.5},
        "discomforts": {"observe_room": 0.1},
        "dominant": "observe_room",
    }
    stores = MagicMock()
    stores.self_narrative.list_active_arcs.return_value = []
    stores.orchestrator.recent_agent_experiences.return_value = [
        MagicMock(
            experience_id="e1",
            ts="2026-06-18T00:00:00+09:00",
            kind="agent_autonomous_action",
            summary="private note",
            importance=3,
        )
    ]
    stores.social_state.get_social_state.side_effect = RuntimeError("skip")
    stores.relationship.list_active_commitments.return_value = []
    mock_get_stores.return_value = stores
    mock_pulse.return_value = AgentPulseView(
        next_wake_at="2026-06-18T09:00:00+09:00",
        next_wake_in_sec=120.0,
        reason="autonomous_tick",
        last_wake_at=None,
        last_action="think_or_discuss_topic",
        dominant_desire="cognitive_load",
        channel="autonomous",
    )
    mock_plan.return_value = PlanPreviewView(
        primary_move="act_autonomously",
        why="dominant desire",
        allowed_actions=["think_or_discuss_topic"],
        forbidden_actions=["nudge_human"],
        quiet_hours_active=False,
        preview_at="2026-06-18T08:00:00+09:00",
    )

    status = fetch_koyori_status(person_id="ma")
    assert len(status.recent_experiences) == 1
    assert status.agent_pulse is not None
    assert status.autonomous_plan is not None
    assert status.autonomous_plan.primary_move == "act_autonomously"
