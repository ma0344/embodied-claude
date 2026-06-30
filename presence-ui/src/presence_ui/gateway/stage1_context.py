"""Stage1 classifier context — open departure loops for contextual greeting (Q3a)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

from social_core.activity_frame import activity_gloss, build_activity_frame_from_detail

from presence_ui.gateway.ol7_return_signal import activity_label_for_loop

if TYPE_CHECKING:
    from presence_ui.deps import PresenceStores


@dataclass(frozen=True, slots=True)
class Stage1DepartureHint:
    loop_id: str
    label: str
    gloss: str
    topic: str


def fetch_stage1_departure_hints(
    stores: PresenceStores,
    *,
    person_id: str,
    limit: int = 8,
) -> tuple[Stage1DepartureHint, ...]:
    """Open loops with activity_frame.mode=departure — for Stage1 Q3a only."""
    loops = stores.relationship.list_open_loops(person_id=person_id, limit=limit)
    hints: list[Stage1DepartureHint] = []
    for loop in loops:
        detail = loop.detail if isinstance(loop.detail, dict) else {}
        frame = build_activity_frame_from_detail(detail)
        if frame is None or frame.mode != "departure":
            continue
        departure = str(detail.get("utterance") or detail.get("source_utterance") or loop.topic)
        event = detail.get("event")
        if isinstance(event, dict):
            what = event.get("what")
            if what and str(what).strip():
                departure = str(what).strip()
        label = activity_label_for_loop(
            topic=loop.topic,
            departure=departure,
            detail=detail,
        )
        gloss = activity_gloss(frame) or label
        hints.append(
            Stage1DepartureHint(
                loop_id=loop.id,
                label=label,
                gloss=gloss,
                topic=loop.topic,
            )
        )
    return tuple(hints)


def append_stage1_departure_context(
    lines: list[str],
    open_departure_loops: Sequence[Stage1DepartureHint],
) -> None:
    if not open_departure_loops:
        lines.append("open_departure_loops: (none)")
        return
    lines.append("open_departure_loops:")
    for i, hint in enumerate(open_departure_loops, 1):
        topic = hint.topic.strip().replace("\n", " ")
        gloss = hint.gloss.strip().replace("\n", " ")
        label = hint.label.strip().replace("\n", " ")
        lines.append(
            f"  {i}. loop_id={hint.loop_id} | label={label} | gloss={gloss} | topic={topic}"
        )
