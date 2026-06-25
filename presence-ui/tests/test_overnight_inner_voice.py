"""Tests for MEM-5f-c overnight inner voice."""

from __future__ import annotations

from social_core.stm import StmEntry

from presence_ui.services.overnight_inner_voice import (
    _fallback_inner_voice,
    collect_overnight_reflection_sources,
    format_overnight_inner_voice_block,
    synthesize_overnight_inner_voice,
)


def _reflection_entry(summary: str) -> StmEntry:
    return StmEntry(
        entry_id="stm_ref",
        ts="2026-06-20T23:00:00+09:00",
        local_day="2026-06-20",
        person_id="ma",
        source="experience_mirror",
        kind="agent_private_reflection",
        summary=summary,
        session_id=None,
        experience_id="exp_1",
        turn_index=None,
        importance=3,
        dreamed_at=None,
        created_at="2026-06-20T23:00:00+09:00",
        metadata_json=None,
    )


def test_format_overnight_inner_voice_block() -> None:
    block = format_overnight_inner_voice_block("まーの体調がちょっと心配やった")
    assert block.startswith("[overnight_inner_voice]")
    assert block.endswith("[/overnight_inner_voice]")


def test_collect_overnight_reflection_sources_strips_noise() -> None:
    entries = [
        _reflection_entry(
            "Autonomous tick during quiet hours — prefer a private note\n\n"
            "いま心に残ってること:\n- まーの一服の時間が穏やかやった"
        )
    ]
    reflections, shifts = collect_overnight_reflection_sources(
        entries,
        person_id="ma",
        local_day="2026-06-20",
        timezone="Asia/Tokyo",
    )
    assert reflections
    assert "Autonomous tick" not in reflections[0]
    assert shifts == []


def test_synthesize_overnight_inner_voice_fallback_without_llm() -> None:
    entries = [
        _reflection_entry("部屋の静けさの中で、まーのペースに合わせようと思った"),
        StmEntry(
            entry_id="stm_shift",
            ts="2026-06-20T22:00:00+09:00",
            local_day="2026-06-20",
            person_id="ma",
            source="experience_mirror",
            kind="interpretation_shift",
            summary="まーは急かされるより余白を好む",
            session_id=None,
            experience_id=None,
            turn_index=None,
            importance=4,
            dreamed_at=None,
            created_at="2026-06-20T22:00:00+09:00",
            metadata_json=None,
        ),
    ]
    block = synthesize_overnight_inner_voice(
        entries,
        person_id="ma",
        local_day="2026-06-20",
        timezone="Asia/Tokyo",
        use_llm=False,
    )
    assert "[overnight_inner_voice]" in block
    assert "解釈" in block or "部屋" in block


def test_fallback_inner_voice_builds_paragraphs() -> None:
    text = _fallback_inner_voice(
        ["テーマA", "テーマB"],
        interpretation_shifts=["shift note"],
    )
    assert "テーマA" in text
    assert "shift note" in text
