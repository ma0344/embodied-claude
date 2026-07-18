"""Tests for cue-gated person_profile_gists surface inject."""

from __future__ import annotations

from interaction_orchestrator_mcp.profile_surface import (
    profile_surface_cued,
    select_profile_gists_for_surface,
)

GISTS = [
    "まーのグループホーム名は「ここっち」（embodied-claude/こよりの「こっち」と別）",
    "まーの仕事・所属: ねっとわん（水曜午前）",
]


def test_uncued_turn_skips_profile_gists() -> None:
    assert not profile_surface_cued("お腹減ったかも")
    assert select_profile_gists_for_surface(GISTS, user_text="お腹減ったかも") == []


def test_cued_turn_injects_overlapping_gist() -> None:
    assert profile_surface_cued("ここっちって何？")
    out = select_profile_gists_for_surface(GISTS, user_text="ここっちって何？")
    assert out
    assert "ここっち" in out[0]


def test_work_cue_prefers_netone_gist() -> None:
    out = select_profile_gists_for_surface(GISTS, user_text="ねっとわんいつ？")
    assert out
    assert any("ねっとわん" in g for g in out)
