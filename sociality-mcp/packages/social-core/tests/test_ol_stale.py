"""Tests for OL-STALE stale_policy."""

from __future__ import annotations

import json
from datetime import date

from social_core.ol_stale import (
    STALE_POLICY_UNTIL_COMPLETED,
    evaluate_stale_close,
    infer_stale_policy_for_loop,
)


def test_infer_until_completed_without_resolved_date() -> None:
    policy, stale_after = infer_stale_policy_for_loop(
        utterance="県に提出する書類を作る",
        loop_topic="県に提出する書類を作る",
        resolved_date=None,
        needs_date_confirmation=False,
    )
    assert policy == STALE_POLICY_UNTIL_COMPLETED
    assert stale_after is None


def test_infer_default_with_resolved_date() -> None:
    policy, _ = infer_stale_policy_for_loop(
        utterance="明日、角煮を作る",
        loop_topic="2026年6月30日、角煮を作る",
        resolved_date=date(2026, 6, 30),
        needs_date_confirmation=False,
        temporal_phrase="明日",
    )
    assert policy == "default"


def test_infer_until_completed_from_cue() -> None:
    policy, _ = infer_stale_policy_for_loop(
        utterance="書類、終わるまで覚えて",
        loop_topic="書類を作る",
        resolved_date=date(2026, 6, 30),
        needs_date_confirmation=False,
    )
    assert policy == STALE_POLICY_UNTIL_COMPLETED


def test_evaluate_skips_until_completed() -> None:
    detail = json.dumps(
        {
            "resolved_date": "2026-06-28",
            "stale_policy": "until_completed",
        }
    )
    assert (
        evaluate_stale_close(
            detail,
            as_of=date(2026, 6, 29),
        )
        is None
    )


def test_evaluate_default_uses_resolved_date() -> None:
    detail = json.dumps({"resolved_date": "2026-06-28", "stale_policy": "default"})
    passed = evaluate_stale_close(detail, as_of=date(2026, 6, 29))
    assert passed == date(2026, 6, 28)


def test_evaluate_until_date_after_stale_after() -> None:
    detail = json.dumps(
        {
            "stale_policy": "until_date",
            "stale_after": "2026-07-04",
        }
    )
    assert evaluate_stale_close(detail, as_of=date(2026, 7, 3)) is None
    assert evaluate_stale_close(detail, as_of=date(2026, 7, 5)) == date(2026, 7, 4)
