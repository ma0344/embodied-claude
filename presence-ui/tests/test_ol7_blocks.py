"""OL7 gateway inject blocks."""

from presence_ui.gateway.ol7_blocks import format_ol7_close_result, format_ol7_pending_block


def test_format_ol7_close_result() -> None:
    block = format_ol7_close_result(closed_topics=["サッカー試合"], summary="見終わった")
    assert "[open_loops_close_result]" in block
    assert "status=ok" in block
    assert "サッカー試合" in block


def test_format_ol7_pending_block() -> None:
    block = format_ol7_pending_block(
        loop_id="loop_x",
        topic="散歩",
        source_utterance="ただいま",
    )
    assert "[loops_due_for_check]" in block
    assert "loop_id=loop_x" in block
    assert "ただいま" in block
