"""Tests for Aozora Bunko passage fetching (LW-1)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from interaction_orchestrator_mcp.schemas import InteractionContext, ResponseContract, ResponsePlan

from presence_ui.gateway import direct_actions
from presence_ui.gateway.aozora import (
    AozoraPassage,
    AozoraWork,
    ReadingState,
    _book_reached_end,
    complete_reading_pause,
    join_passages_from,
    last_passage_index,
    load_reading_state,
    load_works,
    passage_needs_reflect,
    passage_reflect_stuck,
    pick_passage,
    reading_phase,
    save_reading_state,
    split_main_text_passages,
    strip_html_text,
)

_SAMPLE_MAIN = """
<div class="main_text">
<br />
　一節目の本文である。静かな夜に読む短い段落として十分な長さがある。<br />
　二節目はもう少し長い。雨の音を聞きながら、静かに考えていた。<br />
</div>
<div class="bibliographical_information">
"""


def test_strip_html_text_removes_ruby() -> None:
    raw = (
        '<ruby><rb>\u7f85\u751f\u9580</rb><rp>\uff08</rp>'
        '<rt>\u3089\u3057\u3087\u3046\u3082\u3093</rt><rp>\uff09</rp></ruby>'
    )
    assert strip_html_text(raw) == "\u7f85\u751f\u9580"


def test_split_main_text_passages() -> None:
    passages = split_main_text_passages(_SAMPLE_MAIN)
    assert len(passages) == 2
    assert passages[0].startswith("一節目")
    assert "雨の音" in passages[1]


def test_join_passages_from_bundles_short_paragraphs() -> None:
    passages = ["短い一節。", "もう一つ続く段落で、夜の読書に少し足す。"]
    text, next_idx = join_passages_from(passages, 0, max_chars=1600)
    assert "短い一節" in text
    assert "もう一つ" in text
    assert next_idx == 0


def test_passage_reflect_helpers() -> None:
    state = ReadingState(
        phase="pause",
        last_passage={"passage_index": 5, "text": "一節"},
        last_reflected_passage_index=-1,
    )
    assert passage_needs_reflect(state) is True
    assert passage_reflect_stuck(state) is False

    state.last_reflected_passage_index = 5
    assert passage_needs_reflect(state) is False
    assert passage_reflect_stuck(state) is True

    state.phase = "read"
    assert passage_needs_reflect(state) is False
    assert passage_reflect_stuck(state) is False
    assert last_passage_index(state) == 5


def test_pick_passage_single_book_then_pause(tmp_path: Path) -> None:
    work = AozoraWork(
        author_id="000879",
        work_id="127",
        title="羅生門",
        author="芥川龍之介",
        content_file="127_15260.html",
    )
    state_path = tmp_path / "state.json"

    with patch(
        "presence_ui.gateway.aozora.fetch_work_passages",
        return_value=(["passage A", "passage B"], "https://example/a.html"),
    ), patch(
        "presence_ui.gateway.aozora.aozora_passage_max_chars",
        return_value=12,
    ):
        first = pick_passage([work], state_path=state_path)
        assert reading_phase(state_path) == "pause"
        second = pick_passage([work], state_path=state_path)
        complete_reading_pause(
            state_path=state_path,
            reflected_passage_index=0,
        )
        third = pick_passage([work], state_path=state_path)

    assert first is not None
    assert second is None
    assert third is not None
    assert first.text == "passage A"
    assert third.text == "passage B"
    state = load_reading_state(state_path)
    assert state.phase == "pause"
    assert state.active_work is not None
    assert state.active_work["work_id"] == "127"


def test_book_reached_end_wraps_to_zero() -> None:
    assert _book_reached_end(36, 0, 55) is True
    assert _book_reached_end(0, 0, 55) is False
    assert _book_reached_end(5, 6, 10) is False


def test_pick_passage_returns_none_when_close(tmp_path: Path) -> None:
    work = AozoraWork(
        author_id="000879",
        work_id="16",
        title="侏儒の言葉",
        author="芥川龍之介",
        content_file="16_14570.html",
    )
    state_path = tmp_path / "state.json"
    save_reading_state(
        ReadingState(
            phase="close",
            active_work={
                "author_id": "000879",
                "work_id": "16",
                "title": "侏儒の言葉",
                "author": "芥川龍之介",
            },
        ),
        state_path,
    )
    with patch("presence_ui.gateway.aozora.fetch_work_passages") as fetch_mock:
        assert pick_passage([work], state_path=state_path) is None
    fetch_mock.assert_not_called()


def test_complete_reading_pause_caps_reread_same(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PRESENCE_AOZORA_REREAD_SAME_MAX", "2")
    state_path = tmp_path / "state.json"
    base = ReadingState(
        phase="pause",
        passage_index=5,
        last_passage={
            "passage_index": 5,
            "next_passage_index": 6,
            "total_passages": 10,
            "text": "chunk",
        },
    )
    save_reading_state(base, state_path)

    complete_reading_pause(
        next_move="reread_same",
        reflected_passage_index=5,
        state_path=state_path,
    )
    once = load_reading_state(state_path)
    assert once.phase == "read"
    assert once.passage_index == 5
    assert once.reread_same_count == 1

    once.phase = "pause"
    save_reading_state(once, state_path)
    complete_reading_pause(
        next_move="reread_same",
        reflected_passage_index=5,
        state_path=state_path,
    )
    capped = load_reading_state(state_path)
    assert capped.phase == "read"
    assert capped.passage_index == 6
    assert capped.reread_same_count == 0


@pytest.mark.asyncio
async def test_read_stuck_heal_returns_without_pick_passage() -> None:
    stores = MagicMock()
    stuck = ReadingState(
        phase="pause",
        last_passage={
            "passage_index": 3,
            "text": "一節目の本文",
            "title": "侏儒の言葉",
            "author": "芥川龍之介",
            "next_passage_index": 4,
            "total_passages": 10,
        },
        last_reflected_passage_index=3,
    )
    healed = ReadingState(phase="read", passage_index=4)

    with (
        patch(
            "presence_ui.gateway.direct_actions.load_reading_state",
            return_value=stuck,
        ),
        patch(
            "presence_ui.gateway.direct_actions.complete_reading_pause",
            return_value=healed,
        ) as pause_mock,
        patch(
            "presence_ui.gateway.direct_actions.pick_passage",
        ) as pick_mock,
    ):
        outcome = await direct_actions.read_aozora_passage_direct(
            stores,
            person_id="ma",
            ctx=_ctx(),
            plan=_plan(allowed=["read_aozora_passage"]),
        )

    pick_mock.assert_not_called()
    pause_mock.assert_called_once()
    assert outcome.ok is True
    assert outcome.detail == "stuck_heal_advance"


@pytest.mark.asyncio
async def test_read_stuck_heal_chains_close_at_book_end() -> None:
    stores = MagicMock()
    stuck = ReadingState(
        phase="pause",
        last_passage={
            "passage_index": 36,
            "text": "最後の一節",
            "title": "侏儒の言葉",
            "author": "芥川龍之介",
            "next_passage_index": 0,
            "total_passages": 55,
        },
        last_reflected_passage_index=36,
    )
    healed_close = ReadingState(phase="close", passage_index=36)
    close_outcome = direct_actions.DirectActionOutcome(
        ok=True,
        action="close_aozora_reading",
        summary="Book closed.",
        detail="close_ok",
        events=[],
    )

    with (
        patch(
            "presence_ui.gateway.direct_actions.load_reading_state",
            return_value=stuck,
        ),
        patch(
            "presence_ui.gateway.direct_actions.complete_reading_pause",
            return_value=healed_close,
        ),
        patch(
            "presence_ui.gateway.direct_actions.close_aozora_reading_direct",
            return_value=close_outcome,
        ) as close_mock,
        patch("presence_ui.gateway.direct_actions.pick_passage") as pick_mock,
    ):
        outcome = await direct_actions.read_aozora_passage_direct(
            stores,
            person_id="ma",
            ctx=_ctx(),
            plan=_plan(allowed=["read_aozora_passage"]),
        )

    pick_mock.assert_not_called()
    close_mock.assert_called_once()
    assert outcome.ok is True
    assert "Book closed." in outcome.summary


@pytest.mark.asyncio
async def test_read_rejects_close_phase() -> None:
    stores = MagicMock()
    closing = ReadingState(phase="close", active_work={"work_id": "16"})

    with patch(
        "presence_ui.gateway.direct_actions.load_reading_state",
        return_value=closing,
    ):
        outcome = await direct_actions.read_aozora_passage_direct(
            stores,
            person_id="ma",
            ctx=_ctx(),
            plan=_plan(allowed=["read_aozora_passage"]),
        )

    assert outcome.ok is False
    assert outcome.detail == "wrong_phase_close"


def test_complete_reading_pause_advances_to_close_at_book_end(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    save_reading_state(
        ReadingState(
            phase="pause",
            passage_index=36,
            last_passage={
                "passage_index": 36,
                "next_passage_index": 0,
                "total_passages": 55,
                "text": "chunk",
            },
        ),
        state_path,
    )
    after = complete_reading_pause(
        next_move="advance",
        reflected_passage_index=36,
        state_path=state_path,
    )
    assert after.phase == "close"


def test_load_works_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps(
        [
            {
                "author_id": "000879",
                "work_id": "127",
                "title": "羅生門",
                "author": "芥川",
                "content_file": "127_15260.html",
            }
        ]
    )
    monkeypatch.setenv("PRESENCE_AOZORA_WORKS", payload)
    works = load_works()
    assert len(works) == 1
    assert works[0].title == "羅生門"


def _ctx() -> InteractionContext:
    return InteractionContext(
        ts="2026-06-10T12:00:00+00:00",
        local_time="2026-06-10T21:00:00+09:00",
        timezone="Asia/Tokyo",
        agent_state={
            "ts": "2026-06-10T12:00:00+00:00",
            "desires": {},
            "discomforts": {},
            "dominant_desire": "cognitive_load",
            "recent_experiences": [],
            "active_arcs": [],
            "private_reflections": 0,
            "interpretation_shifts": 0,
        },
        response_contract=ResponseContract(),
        prompt_summary="quiet read",
        compact_prompt_block="[desires] cognitive_load",
    )


def _plan(*, allowed: list[str]) -> ResponsePlan:
    return ResponsePlan(
        primary_move="act_autonomously",  # type: ignore[arg-type]
        why_this_move="静かに一節読む",
        tone={"warmth": 0.5, "directness": 0.7, "playfulness": 0.2, "pace": "steady"},
        memory_use={
            "use_specific_memory": False,
            "max_memories_to_surface": 1,
            "avoid_memory_dump": True,
        },
        initiative={
            "level": "low",
            "allowed_actions": allowed,
            "forbidden_actions": [],
        },
        boundary={"quiet_hours_active": True, "privacy_sensitive": False, "notes": []},
    )


@pytest.mark.asyncio
async def test_read_aozora_passage_direct_remembers_and_reflects() -> None:
    stores = MagicMock()
    stores.orchestrator.append_private_reflection.return_value = MagicMock(
        experience_id="ref-aozora"
    )
    work = AozoraWork(
        author_id="000879",
        work_id="127",
        title="\u7f85\u751f\u9580",
        author="\u82a5\u5ddd\u9f8d\u4e4b\u4ecb",
    )
    picked = AozoraPassage(
        work=work,
        text="\u3042\u308b\u65e5\u306e\u66ae\u65b9\u306e\u4e8b\u3067\u3042\u308b\u3002",
        passage_index=0,
        total_passages=3,
        source_url="https://www.aozora.gr.jp/cards/000879/files/127_15260.html",
    )

    with (
        patch(
            "presence_ui.gateway.direct_actions.load_reading_state",
            return_value=ReadingState(phase="read"),
        ),
        patch(
            "presence_ui.gateway.direct_actions.pick_passage",
            return_value=picked,
        ),
        patch(
            "presence_ui.gateway.direct_actions.http_remember",
            return_value={"ok": True, "id": "m-aozora"},
        ),
        patch(
            "presence_ui.gateway.direct_actions.satisfy_desire_direct",
            return_value=(True, "literary_wander"),
        ) as satisfy_mock,
        patch(
            "presence_ui.gateway.direct_actions.inward_autonomous_window",
            return_value=True,
        ),
    ):
        outcome = await direct_actions.execute_autonomous_plan(
            stores,
            person_id="ma",
            ctx=_ctx(),
            plan=_plan(allowed=["read_aozora_passage"]),
        )

    assert outcome.ok is True
    assert outcome.action == "read_aozora_passage"
    assert outcome.desire_satisfied == "literary_wander"
    satisfy_mock.assert_called_once()
    stores.orchestrator.append_private_reflection.assert_not_called()
    stores.orchestrator.record_agent_experience.assert_called_once()
