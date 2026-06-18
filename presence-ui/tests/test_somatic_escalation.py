"""BIO-8d somatic escalation."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from presence_ui.services import body_state as bs
from presence_ui.services.somatic_escalation import maybe_escalate_somatic


@pytest.fixture
def body_path(tmp_path, monkeypatch):
    path = tmp_path / "body_state.json"
    monkeypatch.setattr(bs, "body_state_path", lambda: path)
    return path


def test_maybe_escalate_skips_when_none(body_path) -> None:
    stores = MagicMock()
    result = maybe_escalate_somatic(stores, person_id="ma")
    assert result["level"] == "none"
    stores.boundary.evaluate_action.assert_not_called()


def test_maybe_escalate_critical_pushes(body_path, monkeypatch) -> None:
    state = bs.load_body_state()
    bs.note_organ_probe(state, organ="eyes", status="failed", summary="offline")
    bs.note_organ_probe(state, organ="voice", status="failed", summary="tts down")
    bs.save_body_state(state)

    stores = MagicMock()
    stores.boundary.evaluate_action.return_value = MagicMock(decision="allow")

    pushed: list[str] = []

    def fake_push(*, text: str, **kwargs):
        pushed.append(text)
        return True, "ntfy:ok"

    monkeypatch.setattr(
        "presence_ui.services.outbound_push.send_outbound_push",
        fake_push,
    )

    result = maybe_escalate_somatic(stores, person_id="ma")
    assert result["level"] == "critical"
    assert result["push"] == "ok"
    assert pushed
    assert "目" in pushed[0]
    stores.orchestrator.record_agent_experience.assert_called_once()


def test_maybe_escalate_respects_cooldown(body_path, monkeypatch) -> None:
    state = bs.load_body_state()
    bs.note_organ_probe(state, organ="eyes", status="failed", summary="offline")
    bs.note_organ_probe(state, organ="voice", status="failed", summary="tts down")
    bs.mark_escalation_push(state, level="critical")
    bs.save_body_state(state)

    stores = MagicMock()
    stores.boundary.evaluate_action.return_value = MagicMock(decision="allow")
    monkeypatch.setattr(
        "presence_ui.services.outbound_push.send_outbound_push",
        lambda **k: (True, "ntfy:ok"),
    )

    result = maybe_escalate_somatic(stores, person_id="ma")
    assert result["level"] == "critical"
    assert result["push"] == "cooldown"
