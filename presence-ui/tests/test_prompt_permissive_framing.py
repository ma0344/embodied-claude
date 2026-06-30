"""Prompt framing — permissive collocation (POC 間違いではない)."""

from __future__ import annotations

from presence_ui.gateway.ol7_return_signal import OL7_SYSTEM
from presence_ui.gateway.ol_gate_prompts import STAGE1_SYSTEM


def test_stage1_uses_permissive_framing_not_appropriate_only() -> None:
    assert "間違い" in STAGE1_SYSTEM
    assert "適切か" in STAGE1_SYSTEM  # negation: do not judge by 適切
    assert "POC" in STAGE1_SYSTEM
    assert "昼寝してくる" in STAGE1_SYSTEM
    assert "おはよう（open_departure=昼寝" in STAGE1_SYSTEM


def test_stage1_q3a_avoids_natural_wording() -> None:
    q3a_start = STAGE1_SYSTEM.index("**Q3a")
    q4_start = STAGE1_SYSTEM.index("**Q4")
    q3a_block = STAGE1_SYSTEM[q3a_start:q4_start]
    assert "間違いではない" in q3a_block
    assert "自然" not in q3a_block


def test_ol7_uses_permissive_framing() -> None:
    assert "間違い" in OL7_SYSTEM
    assert "適切か" in OL7_SYSTEM
    assert "おはよう + 昼寝 departure" in OL7_SYSTEM
    assert "就寝" in OL7_SYSTEM
