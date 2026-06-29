"""MEM-4 memory layer compose injection tests."""

from __future__ import annotations

from interaction_orchestrator_mcp.schemas import InteractionContext, ResponseContract

from presence_ui.services.dream_digest import DreamDigestRecord, save_dream_digest
from presence_ui.services.memory_context import (
    build_dream_digest_block,
    build_overnight_inner_voice_block,
    enrich_memory_context,
)


def _ctx(*, local_time: str = "2026-06-18T08:00:00+09:00") -> InteractionContext:
    return InteractionContext(
        ts="2026-06-18T00:00:00+00:00",
        local_time=local_time,
        timezone="Asia/Tokyo",
        agent_state={
            "ts": "2026-06-18T00:00:00+00:00",
            "desires": {},
            "discomforts": {},
            "recent_experiences": [],
            "active_arcs": [],
            "private_reflections": 0,
            "interpretation_shifts": 0,
        },
        response_contract=ResponseContract(),
        prompt_summary="test",
        compact_prompt_block="[base]",
    )


def test_dream_digest_block_reanchors_yesterday_today(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESENCE_DREAM_DIGEST_PATH", str(tmp_path / "dream.json"))
    save_dream_digest(
        DreamDigestRecord(
            dreamed_at="2026-06-18T03:00:00+09:00",
            local_day="2026-06-17",
            summary="[dream_digest]\n- (open_loop_progress) 今日は入浴介助\n[/dream_digest]",
            stm_entry_ids=["stm_1"],
        )
    )
    morning = build_dream_digest_block(
        local_time="2026-06-18T08:00:00+09:00",
        timezone="Asia/Tokyo",
    )
    assert "昨日" in morning
    assert "今日は入浴" not in morning


def test_dream_digest_block_only_in_morning(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESENCE_DREAM_DIGEST_PATH", str(tmp_path / "dream.json"))
    save_dream_digest(
        DreamDigestRecord(
            dreamed_at="2026-06-18T03:00:00+09:00",
            local_day="2026-06-17",
            summary="[dream_digest]\n- (episode_close) 天気の話\n[/dream_digest]",
            stm_entry_ids=["stm_1"],
        )
    )
    morning = build_dream_digest_block(
        local_time="2026-06-18T08:00:00+09:00",
        timezone="Asia/Tokyo",
    )
    afternoon = build_dream_digest_block(
        local_time="2026-06-18T14:00:00+09:00",
        timezone="Asia/Tokyo",
    )
    assert "天気" in morning
    assert "2026-06-17" in morning
    assert "今日は 2026-06-18" in morning
    assert afternoon == ""


def test_enrich_memory_context_appends_blocks(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESENCE_DREAM_DIGEST_PATH", str(tmp_path / "dream.json"))
    save_dream_digest(
        DreamDigestRecord(
            dreamed_at="2026-06-18T03:00:00+09:00",
            local_day="2026-06-17",
            summary="[dream_digest]\n- overnight note\n[/dream_digest]",
            stm_entry_ids=[],
        )
    )
    ctx = enrich_memory_context(_ctx(), channel="chat")
    assert "[base]" in ctx.compact_prompt_block
    assert "overnight note" in ctx.compact_prompt_block


def test_overnight_inner_voice_block_only_in_morning(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESENCE_DREAM_DIGEST_PATH", str(tmp_path / "dream.json"))
    save_dream_digest(
        DreamDigestRecord(
            dreamed_at="2026-06-18T03:00:00+09:00",
            local_day="2026-06-17",
            summary="[dream_digest]\n- note\n[/dream_digest]",
            stm_entry_ids=["stm_1"],
            inner_voice_summary="[overnight_inner_voice]\n昨夜は穏やかやった\n[/overnight_inner_voice]",
        )
    )
    morning = build_overnight_inner_voice_block(
        local_time="2026-06-18T08:00:00+09:00",
        timezone="Asia/Tokyo",
    )
    afternoon = build_overnight_inner_voice_block(
        local_time="2026-06-18T14:00:00+09:00",
        timezone="Asia/Tokyo",
    )
    assert "昨夜は穏やか" in morning
    assert "2026-06-17" in morning
    assert "今日は 2026-06-18" in morning
    assert afternoon == ""
