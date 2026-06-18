"""BIO-8b body_state registry."""

from __future__ import annotations

import json

import pytest

from presence_ui.services import body_state as bs


@pytest.fixture
def body_path(tmp_path, monkeypatch):
    path = tmp_path / "body_state.json"
    monkeypatch.setattr(bs, "body_state_path", lambda: path)
    return path


def test_affliction_creates_pending_report(body_path) -> None:
    state = bs.load_body_state()
    report = bs.note_organ_affliction(
        state,
        organ="eyes",
        summary="目が開かへんかった",
        action="camera_look_around",
        remedy="qwen_reload",
    )
    bs.save_body_state(state)
    assert report.organ == "eyes"
    assert state.organs["eyes"].status == "failed"
    pending = bs.unreported_pending(state)
    assert len(pending) == 1
    data = json.loads(body_path.read_text(encoding="utf-8"))
    assert data["pending_reports"][0]["summary"] == "目が開かへんかった"


def test_organ_ok_resolves_pending(body_path) -> None:
    state = bs.load_body_state()
    bs.note_organ_affliction(
        state,
        organ="eyes",
        summary="目が曇ってた",
        action="see",
    )
    bs.note_organ_ok(state, organ="eyes", note="窓が見える")
    pending = bs.unreported_pending(state)
    assert pending == []
    assert state.organs["eyes"].status == "ok"


def test_somatic_state_dict_degraded(body_path) -> None:
    state = bs.load_body_state()
    bs.note_organ_affliction(
        state,
        organ="voice",
        summary="声が出せへん",
        action="say",
        status="degraded",
    )
    somatic = bs.somatic_state_dict(state)
    assert somatic["degraded_organs"][0]["organ"] == "voice"
    assert len(somatic["pending_unreported"]) == 1


def test_compute_escalation_critical_multi_failed(body_path) -> None:
    state = bs.load_body_state()
    bs.note_organ_probe(state, organ="eyes", status="failed", summary="camera offline")
    bs.note_organ_probe(state, organ="voice", status="failed", summary="tts down")
    esc = bs.compute_escalation(state)
    assert esc["level"] == "critical"
    assert esc["failed_count"] == 2


def test_compute_escalation_elevated_two_degraded(body_path) -> None:
    state = bs.load_body_state()
    bs.note_organ_probe(state, organ="eyes", status="degraded", summary="blur")
    bs.note_organ_probe(state, organ="mind", status="degraded", summary="memory slow")
    esc = bs.compute_escalation(state)
    assert esc["level"] == "elevated"
