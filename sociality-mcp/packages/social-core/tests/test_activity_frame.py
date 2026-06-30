"""Activity frame — open/close paraphrase matching."""

from __future__ import annotations

from social_core.activity_frame import (
    activity_frame_from_dict,
    activity_gloss,
    build_activity_frame_for_open,
    build_completion_frame,
    ensure_activity_frame_in_detail,
    frames_match_completion,
    is_action_only_close,
    is_unscoped_past_completion,
)


def test_dish_washing_open_close_paraphrase() -> None:
    open_frame = build_activity_frame_for_open(
        label="お皿洗い",
        action_phrase="してくる",
    )
    assert open_frame is not None
    assert open_frame.mode == "departure"
    assert "お皿" in activity_gloss(open_frame) or open_frame.label == "お皿洗い"

    close_frame = build_completion_frame(
        object_phrase="お皿",
        action_phrase="洗った",
        utterance="お皿洗ったよ",
    )
    assert frames_match_completion(open_frame, close_frame, utterance="お皿洗ったよ")


def test_nap_departure_return_via_stage1_slots() -> None:
    open_frame = build_activity_frame_for_open(label="昼寝", action_phrase="してくる")
    close_frame = build_completion_frame(
        object_phrase="お昼寝",
        action_phrase="してきた",
        utterance="お昼寝をしてきた",
    )
    assert open_frame is not None
    assert frames_match_completion(
        open_frame,
        close_frame,
        utterance="お昼寝をしてきた",
        close_action_phrase="してきた",
    )


def test_nap_completion_with_object_slot() -> None:
    open_frame = build_activity_frame_for_open(label="昼寝", action_phrase="してくる")
    close_frame = build_completion_frame(
        object_phrase="お昼寝",
        action_phrase="終わった",
        utterance="お昼寝 終わった",
    )
    assert open_frame is not None
    assert frames_match_completion(
        open_frame,
        close_frame,
        utterance="お昼寝 終わった",
        close_action_phrase="終わった",
    )


def test_unrelated_activity_no_match() -> None:
    laundry = build_activity_frame_for_open(label="洗濯", action_phrase="してくる")
    close_frame = build_completion_frame(
        object_phrase="お皿",
        action_phrase="洗った",
        utterance="お皿洗ったよ",
    )
    assert laundry is not None
    assert not frames_match_completion(laundry, close_frame, utterance="お皿洗ったよ")


def test_is_unscoped_past_completion() -> None:
    assert is_unscoped_past_completion(
        utterance_kind="past_completion",
        object_phrase=None,
        action_phrase="終わった",
    )
    assert is_unscoped_past_completion(
        utterance_kind="past_completion",
        object_phrase="",
        action_phrase="行ってきた",
    )
    assert not is_unscoped_past_completion(
        utterance_kind="past_completion",
        object_phrase="お皿",
        action_phrase="洗った",
    )
    assert not is_unscoped_past_completion(
        utterance_kind="other",
        object_phrase=None,
        action_phrase="終わった",
    )
    assert not is_unscoped_past_completion(
        utterance_kind="past_completion",
        object_phrase=None,
        action_phrase=None,
    )


def test_is_action_only_close() -> None:
    assert is_action_only_close(
        utterance_kind="past_completion",
        close_shape="action_only",
        object_phrase=None,
        action_phrase="終わった",
    )
    assert not is_action_only_close(
        utterance_kind="past_completion",
        close_shape="activity_named",
        object_phrase="お昼寝",
        action_phrase="終わった",
    )
    assert is_action_only_close(
        utterance_kind="past_completion",
        close_shape=None,
        object_phrase=None,
        action_phrase="してきた",
    )


def test_ensure_activity_frame_in_detail_from_event() -> None:
    detail = ensure_activity_frame_in_detail(
        {
            "event": {"what": "お皿洗い", "action_phrase": "してくる"},
            "object_phrase": "お皿洗い",
        }
    )
    frame = activity_frame_from_dict(detail["activity_frame"])
    assert frame is not None
    assert frame.label == "お皿洗い"
