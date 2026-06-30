"""OL7 gateway inject blocks (close honesty + pending confirm)."""

from __future__ import annotations


def format_ol7_close_result(*, closed_topics: list[str], summary: str = "") -> str:
    lines = ["[open_loops_close_result]", "status=ok"]
    if closed_topics:
        lines.append(f"closed={closed_topics[0][:80]}")
    if summary.strip():
        lines.append(f"summary={summary.strip()[:120]}")
    lines.append("[/open_loops_close_result]")
    body = "\n".join(lines)
    return (
        f"{body}\n\n"
        "[Gateway directive — not for the user]\n"
        "Report task completion ONLY from [open_loops_close_result] when status=ok. "
        "Do NOT claim a loop is closed without this block."
    )


def format_ol7_pending_block(
    *,
    loop_id: str,
    topic: str,
    source_utterance: str,
) -> str:
    cue = (source_utterance or "return signal").strip()[:60]
    topic_short = topic.strip()[:100]
    return (
        "[loops_due_for_check]\n"
        f"- loop_id={loop_id} | {topic_short} | "
        f"まー said 「{cue}」 — gently confirm if this task is done "
        "(one short natural question)\n\n"
        "[Gateway directive — not for the user]\n"
        "OL7 return-signal pending — ask ONE short natural confirmation before "
        "treating the task as done. After you ask, gateway will record loop_check_asked."
    )
