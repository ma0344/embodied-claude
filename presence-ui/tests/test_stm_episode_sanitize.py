"""MEM-5g — episode_close summarization strips gateway injection."""

from __future__ import annotations

import pytest

from presence_ui.services.stm_episode import summarize_episode_for_stm


@pytest.mark.asyncio
async def test_summarize_episode_for_stm_strips_gateway_from_ma_turns() -> None:
    enriched = """[gateway_turn_context — not for the user]
[Social context]
[interaction_context]
phase=chat

今は晩ごはんをたべ終わって一服してるとこ"""
    turns = [
        {"sender": "ma", "message": enriched},
        {"sender": "koyori", "message": "あー、お疲れさま！ゆっくりしといて"},
    ]
    summary = await summarize_episode_for_stm(turns, use_llm=False)
    assert summary is not None
    assert "gateway_turn_context" not in summary
    assert "晩ごはん" in summary
    assert "お疲れさま" in summary


@pytest.mark.asyncio
async def test_summarize_episode_for_stm_drops_koyori_echo() -> None:
    turns = [
        {"sender": "koyori", "message": "まー、おる？"},
        {"sender": "ma", "message": "おるよ〜 おはよう。"},
        {"sender": "koyori", "message": "おるよ〜 おはよう。"},
    ]
    summary = await summarize_episode_for_stm(turns, use_llm=False)
    assert summary is not None
    assert "こより: おるよ〜 おはよう。" not in summary
    assert "まー: おるよ〜 おはよう。" in summary
