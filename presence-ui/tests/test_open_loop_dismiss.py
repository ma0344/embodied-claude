"""open_loop_dismiss gateway notes."""

from presence_ui.gateway.open_loop_dismiss import dismiss_note, dismiss_progress_label


def test_dismiss_note_includes_loops_and_commitments() -> None:
    note = dismiss_note(
        closed_loops=["pr review"],
        cancelled_commitments=["remind about PR review"],
    )
    assert "closed_loops: pr review" in note
    assert "cancelled_commitments: remind about PR review" in note
    assert "cancelled commitments" in note.lower()


def test_dismiss_progress_label_both() -> None:
    label = dismiss_progress_label(
        closed_loops=["pr review"],
        cancelled_commitments=["PR review reminder"],
    )
    assert "閉じた" in label
    assert "取り消した" in label
