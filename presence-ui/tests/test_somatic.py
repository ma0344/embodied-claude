"""BIO-8a somatic affliction recording."""

from unittest.mock import MagicMock

from presence_ui.services.somatic import (
    eye_affliction_summary,
    maybe_record_eye_affliction,
    record_body_affliction,
)
from presence_ui.services.vision_capture import VisionCaptureResult


def _vision(*, ok: bool = True, caption: str | None = None, corrupt: bool = False) -> VisionCaptureResult:
    return VisionCaptureResult(
        ok=ok,
        mode="look_around",
        label="center",
        mcp_text="",
        caption=caption,
        file_path="/tmp/x.jpg" if ok else None,
        error=None if ok else "capture failed",
        vision_corrupt=corrupt,
    )


def test_eye_affliction_summary_none_when_healthy() -> None:
    assert eye_affliction_summary(action="camera_look_around", vision=_vision(caption="部屋")) is None


def test_eye_affliction_summary_none_when_capture_ok_but_no_caption() -> None:
    """Describe failure alone must not mark eyes as failed."""
    assert eye_affliction_summary(action="camera_look_outside", vision=_vision(caption=None)) is None


def test_note_eyes_multimodal_see_ok_clears_failed(tmp_path, monkeypatch) -> None:
    from presence_ui.services import body_state as bs
    from presence_ui.services.somatic import note_eyes_multimodal_see_ok

    path = tmp_path / "body_state.json"
    monkeypatch.setattr(bs, "body_state_path", lambda: path)
    state = bs.load_body_state()
    bs.note_organ_affliction(
        state,
        organ="eyes",
        summary="目が開かへんかった",
        action="test",
    )
    bs.save_body_state(state)

    assert note_eyes_multimodal_see_ok(see_mode="current") is True
    loaded = bs.load_body_state()
    assert loaded.organs["eyes"].status == "ok"


def test_eye_affliction_summary_capture_failed() -> None:
    text = eye_affliction_summary(
        action="camera_look_around",
        error="cooldown",
        capture_failed=True,
    )
    assert text is not None
    assert "目が開かへんかった" in text
    assert "cooldown" in text


def test_eye_affliction_summary_vision_corrupt() -> None:
    text = eye_affliction_summary(
        action="camera_look_outside",
        vision=_vision(caption=None, corrupt=True),
    )
    assert text is not None
    assert "曇ってた" in text


def test_maybe_record_eye_affliction_writes_experience(tmp_path, monkeypatch) -> None:
    from presence_ui.services import body_state as bs

    path = tmp_path / "body_state.json"
    monkeypatch.setattr(bs, "body_state_path", lambda: path)
    stores = MagicMock()
    summary = maybe_record_eye_affliction(
        stores,
        person_id="ma",
        action="camera_look_around",
        error="offline",
        capture_failed=True,
    )
    assert summary is not None
    stores.orchestrator.record_agent_experience.assert_called_once()
    payload = stores.orchestrator.record_agent_experience.call_args[0][0]
    assert payload.kind == "body_affliction"
    assert payload.importance == 4
    state = bs.load_body_state()
    assert state.organs["eyes"].status == "failed"
    assert len(bs.unreported_pending(state)) == 1


def test_record_body_affliction_skips_when_healthy() -> None:
    stores = MagicMock()
    assert (
        maybe_record_eye_affliction(
            stores,
            person_id="ma",
            action="camera_look_around",
            vision=_vision(caption="窓が見える"),
        )
        is None
    )
    stores.orchestrator.record_agent_experience.assert_not_called()


def test_record_body_affliction_organ_metadata() -> None:
    stores = MagicMock()
    record_body_affliction(
        stores,
        person_id="ma",
        organ="eyes",
        summary="目が…",
        action="see_current",
        remedy="vision_reload",
    )
    payload = stores.orchestrator.record_agent_experience.call_args[0][0]
    assert payload.felt_state == {"organ": "eyes", "action": "see_current"}
    assert payload.artifacts[1]["remedy_attempted"] == "vision_reload"
