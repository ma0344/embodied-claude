"""TEMP-C Stage2 prompt builders — kind-specific system + Stage1 slot hints."""

from presence_ui.gateway.ol_gate_prompts import (
    build_temp_c_stage2_system,
    build_temp_c_stage2_task,
)


def test_stage2_system_mentions_kind_in_opening() -> None:
    system = build_temp_c_stage2_system(utterance_kind="past_completion")
    assert "past_completion" in system
    assert "やり終えた報告" in system
    assert "what=null" in system or "what=null ·" in system


def test_stage2_task_includes_stage1_slots() -> None:
    task = build_temp_c_stage2_task(
        utterance="試合、見終わった",
        utterance_kind="past_completion",
        object_phrase="試合",
        action_phrase="見終わった",
    )
    assert "stage1_object_phrase: 試合" in task
    assert "stage1_action_phrase: 見終わった" in task
    assert "utterance_kind: past_completion" in task
