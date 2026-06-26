"""Tests for LW-READ pause/close prompts."""

from __future__ import annotations

from presence_ui.gateway.reading_prompts import (
    PAUSE_RESPONSE_SCHEMA,
    build_close_book_reflection,
    build_gw_s1_pause_task,
    build_pause_reflection_v0,
)


def test_pause_reflection_v0_includes_title_and_excerpt() -> None:
    body = build_pause_reflection_v0(
        title="羅生門",
        author="芥川龍之介",
        passage="下人は、大きな嚔をして。",
        passage_index=2,
        total_passages=40,
        sections_this_session=3,
    )
    assert "羅生門" in body
    assert "咀嚼" in body
    assert "下人" in body


def test_gw_s1_task_requests_json_only() -> None:
    task = build_gw_s1_pause_task(
        title="妙な話",
        author="芥川龍之介",
        passage="千枝子は咄嗟に",
        passage_index=0,
        total_passages=20,
        sections_this_session=1,
        prior_hooks=["赤帽の挨拶"],
    )
    assert "gateway_internal" in task
    assert "next_move" in task
    assert "赤帽" in task
    assert "JSON のみ" in task
    assert "つまらなかった" in task


def test_pause_schema_has_required_fields() -> None:
    assert set(PAUSE_RESPONSE_SCHEMA["required"]) == {"hook", "felt", "next_move"}


def test_close_book_reflection() -> None:
    body = build_close_book_reflection(
        title="羅生門",
        author="芥川",
        sections_read=12,
        last_hook="下人の勇気",
    )
    assert "閉じた" in body
    assert "12" in body
    assert "下人の勇気" in body
