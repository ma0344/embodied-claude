"""Stage1 utterance taxonomy — shared by TEMP-C, OL-GATE, and downstream routing."""

from __future__ import annotations

STAGE1_KINDS = frozenset(
    {
        "future_commitment",
        "past_completion",
        "past_report",
        "greeting",
        "correction",
        "calendar_read",
        "calendar_write",
        "other",
    }
)

CLOSE_SHAPES = frozenset({"activity_named", "action_only"})

# kind → downstream (see docs/tracks/stage1-loop-routing.md)
STAGE1_ROUTES: dict[str, str] = {
    "future_commitment": "stage2_open",
    "past_completion": "ol5_ol7_close",
    "past_report": "no_loop",
    "greeting": "no_loop",
    "correction": "correction_route",
    "calendar_read": "calendar_read_gapi",
    "calendar_write": "calendar_gapi",
    "other": "no_loop",
}
