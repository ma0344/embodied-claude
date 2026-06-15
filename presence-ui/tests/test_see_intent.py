"""Tests for see-intent detection (gateway vision prefetch A)."""

from presence_ui.gateway.see_intent import detect_ptz_intent, detect_see_intent


def test_detect_see_current() -> None:
    intent = detect_see_intent("何が見える？")
    assert intent is not None
    assert intent.mode == "current"


def test_detect_see_window() -> None:
    intent = detect_see_intent("窓の外どう？")
    assert intent is not None
    assert intent.mode == "window"


def test_detect_see_desk() -> None:
    intent = detect_see_intent("まーのデスク見て")
    assert intent is not None
    assert intent.mode == "desk"


def test_detect_see_desk_try_phrasing() -> None:
    intent = detect_see_intent("まーのデスクを見るの試してみて")
    assert intent is not None
    assert intent.mode == "desk"


def test_detect_see_dining() -> None:
    intent = detect_see_intent("ダイニングの様子どう？")
    assert intent is not None
    assert intent.mode == "dining"


def test_detect_see_desk_without_cue_is_none() -> None:
    assert detect_see_intent("まーのデスク") is None


def test_detect_see_look_around() -> None:
    intent = detect_see_intent("部屋を見渡して")
    assert intent is not None
    assert intent.mode == "look_around"


def test_detect_see_excludes_memory_recall() -> None:
    assert detect_see_intent("前に見た部屋覚えてる？") is None


def test_detect_see_english() -> None:
    intent = detect_see_intent("what do you see?")
    assert intent is not None
    assert intent.mode == "current"


def test_detect_ptz_left() -> None:
    intent = detect_ptz_intent("左を向いて")
    assert intent is not None
    assert intent.direction == "left"


def test_detect_ptz_right_english() -> None:
    intent = detect_ptz_intent("look right a bit")
    assert intent is not None
    assert intent.direction == "right"
