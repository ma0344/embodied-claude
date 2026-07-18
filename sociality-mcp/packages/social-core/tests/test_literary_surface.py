"""LW-READ literary surface markers."""

from __future__ import annotations

from social_core.literary_surface import is_literary_agent_surface
from social_core.stm import StmEntry, build_stm_prompt_block
from social_core.stm_dreaming import select_episodic_digest_entries


def _entry(summary: str, *, kind: str = "agent_autonomous_action") -> StmEntry:
    return StmEntry(
        entry_id="e1",
        ts="2026-07-18T01:00:00+00:00",
        local_day="2026-07-18",
        person_id="ma",
        source="experience_mirror",
        kind=kind,
        summary=summary,
        session_id=None,
        experience_id=None,
        turn_index=None,
        importance=4,
        dreamed_at=None,
        created_at="2026-07-18T01:00:00+00:00",
        metadata_json="{}",
    )


def test_literary_prefixes() -> None:
    assert is_literary_agent_surface("青空文庫で読んだ『羅生門』— 下人は")
    assert is_literary_agent_surface("青空『羅生門』を読んだ")
    assert is_literary_agent_surface("（青空を読んだあと — 咀嚼）\n本文")
    assert not is_literary_agent_surface("まーと散歩の約束をした")
    assert not is_literary_agent_surface("羅生門どうやった？")


def test_overnight_contaminated() -> None:
    from social_core.literary_surface import is_literary_overnight_contaminated

    assert is_literary_overnight_contaminated(
        "昨日は『羅生門』を読み進めて、下人の葛藤に引っかかってた"
    )
    assert not is_literary_overnight_contaminated(
        "昨日は天気の話と、まーの体調が気になってた"
    )


def test_digest_excludes_literary() -> None:
    entries = [
        _entry("青空『羅生門』— 下人は、老婆をつき放すと"),
        _entry("まーと散歩の約束をした", kind="episode_close"),
    ]
    selected = select_episodic_digest_entries(entries)
    assert len(selected) == 1
    assert "散歩" in selected[0].summary


def test_stm_prompt_skips_literary() -> None:
    block = build_stm_prompt_block(
        [
            _entry("青空『羅生門』を読んだ"),
            _entry("部屋を見た", kind="agent_observation"),
        ]
    )
    assert "羅生門" not in block
    assert "部屋" in block
