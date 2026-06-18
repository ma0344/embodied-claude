"""prompt_block_safe — paired tag truncate + JSONL repair."""

from __future__ import annotations

from presence_ui.gateway.prompt_block_safe import (
    close_open_paired_tags,
    has_unclosed_paired_tags,
    repair_enriched_user_prompt,
    truncate_prompt_text,
)


def test_truncate_closes_stm_recent():
    inner = "- (open_loop_progress) " + ("x" * 3000)
    block = f"[stm_recent]\n{inner}"
    out = truncate_prompt_text(block, 500)
    assert "[stm_recent]" in out
    assert "[/stm_recent]" in out
    assert len(out) <= 500 + len("\n[/stm_recent]") + 2


def test_repair_gateway_prompt_inserts_close_before_user_tail():
    raw = """[gateway_turn_context — not for the user]
[stm_recent]
- (episode_close) 長い要約
……うん、疲れた

こんばんは"""
    fixed = repair_enriched_user_prompt(raw)
    assert "[/stm_recent]" in fixed
    assert fixed.endswith("こんばんは")
    assert fixed.index("[/stm_recent]") < fixed.index("こんばんは")


def test_has_unclosed_detects_missing_close():
    assert has_unclosed_paired_tags("[stm_recent]\n- (x) a")
    assert not has_unclosed_paired_tags("[stm_recent]\n- (x) a\n[/stm_recent]")
