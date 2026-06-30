"""Ingest hook failure visibility."""

from presence_ui.gateway.ingest_hooks import (
    clear_recent_ingest_hook_failures,
    record_ingest_hook_failure,
    recent_ingest_hook_failures,
)


def test_record_ingest_hook_failure_ring_buffer() -> None:
    clear_recent_ingest_hook_failures()
    record_ingest_hook_failure("ol7_return_signal", RuntimeError("thread mismatch"))
    recent = recent_ingest_hook_failures(limit=5)
    assert len(recent) == 1
    assert recent[0]["hook"] == "ol7_return_signal"
    assert recent[0]["error_type"] == "RuntimeError"
    assert "thread mismatch" in recent[0]["message"]
    clear_recent_ingest_hook_failures()
