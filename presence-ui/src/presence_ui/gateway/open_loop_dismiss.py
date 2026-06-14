"""Gateway notes when human dismisses / forgets open loops and commitments."""


def dismiss_note(
    *,
    closed_loops: list[str],
    cancelled_commitments: list[str],
) -> str:
    lines = ["[open_loop_dismiss]"]
    if closed_loops:
        lines.append(f"closed_loops: {', '.join(closed_loops[:5])}")
    if cancelled_commitments:
        lines.append(f"cancelled_commitments: {', '.join(cancelled_commitments[:5])}")
    body = "\n".join(lines)
    return (
        f"{body}\n"
        "\n"
        "[Gateway directive — not for the user]\n"
        "まー explicitly cancelled/forgot the thread(s) above. "
        "Closed loops and cancelled commitments must NOT be revived as "
        "open loops, commitments, or follow-ups. "
        "Acknowledge briefly if relevant; do not re-offer dismissed plans."
    )


def dismiss_progress_label(
    *,
    closed_loops: list[str],
    cancelled_commitments: list[str],
) -> str:
    parts: list[str] = []
    if closed_loops:
        parts.append(
            f"「{closed_loops[0]}」を閉じた"
            if len(closed_loops) == 1
            else "話の続きを閉じた"
        )
    if cancelled_commitments:
        parts.append(
            f"約束「{cancelled_commitments[0]}」を取り消した"
            if len(cancelled_commitments) == 1
            else "約束を取り消した"
        )
    return " · ".join(parts) if parts else "予定を取り消した"
