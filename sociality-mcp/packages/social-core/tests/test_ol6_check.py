"""OL6/OL7 shared pending_check confirm patterns."""

from social_core.ol6_check import (
    PENDING_TRIGGER_OL7,
    is_ol6_completion_confirm,
    is_pending_completion_confirm,
)


def test_ol6_confirm_still_works() -> None:
    assert is_ol6_completion_confirm("終わったよ")


def test_ol7_affirm_after_confirm_question() -> None:
    assert is_pending_completion_confirm(
        "うん、気持ちよかった～",
        trigger=PENDING_TRIGGER_OL7,
    )


def test_ol7_plain_uhn() -> None:
    assert is_pending_completion_confirm("うん", trigger=PENDING_TRIGGER_OL7)


def test_ol7_affirm_not_used_for_ol6_trigger() -> None:
    assert not is_pending_completion_confirm(
        "うん、気持ちよかった",
        trigger="post_deadline_first_turn",
    )
