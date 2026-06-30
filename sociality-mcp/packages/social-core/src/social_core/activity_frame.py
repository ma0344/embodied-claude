"""Activity frame — shared event-noun + action representation for loop open/close.

Completion vs non-completion (疲れた / 頭痛 / これから行く) is **not** decided here.
GW-S2 Stage1 ``utterance_kind=past_completion`` is the e4b completion gate (POC: TRUE/FALSE).
This module only pairs a past_completion utterance with an open loop's activity card.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Open-loop departure labeling only (future_commitment action slot at create time).
_DEPARTURE_ACTION_MARKERS = ("行く", "行って", "してくる", "出かけ", "出かける")


@dataclass(frozen=True, slots=True)
class ActivityFrame:
    """Canonical activity card stored on open loops and used at close."""

    label: str
    object_phrase: str | None = None
    action_stem: str | None = None
    mode: str | None = None


def normalize_action_stem(action_phrase: str | None) -> str | None:
    """Rough verb stem for frame match (洗った→洗, 洗う→洗)."""
    raw = (action_phrase or "").strip()
    if not raw:
        return None
    stem = raw
    for suffix in (
        "ました",
        "してきた",
        "てきた",
        "してくる",
        "している",
        "したよ",
        "した",
        "った",
        "たよ",
        "た",
        "る",
    ):
        if stem.endswith(suffix) and len(stem) > len(suffix):
            stem = stem[: -len(suffix)]
            break
    stem = stem.strip()
    if len(stem) >= 2:
        return stem[:2]
    return stem or None


def activity_gloss(frame: ActivityFrame) -> str:
    if frame.object_phrase and frame.action_stem:
        return f"{frame.object_phrase}を{frame.action_stem}行為"
    return frame.label


def activity_frame_to_dict(frame: ActivityFrame) -> dict[str, str | None]:
    return {
        "label": frame.label,
        "object_phrase": frame.object_phrase,
        "action_stem": frame.action_stem,
        "mode": frame.mode,
        "gloss": activity_gloss(frame),
    }


def activity_frame_from_dict(raw: dict[str, Any]) -> ActivityFrame | None:
    label = str(raw.get("label") or "").strip()
    if not label:
        return None
    obj = str(raw.get("object_phrase") or "").strip() or None
    stem = str(raw.get("action_stem") or "").strip() or None
    mode = str(raw.get("mode") or "").strip() or None
    return ActivityFrame(label=label, object_phrase=obj, action_stem=stem, mode=mode)


def _is_departure_action(action_phrase: str | None) -> bool:
    text = (action_phrase or "").strip()
    return bool(text) and any(marker in text for marker in _DEPARTURE_ACTION_MARKERS)


def build_activity_frame_for_open(
    *,
    label: str,
    object_phrase: str | None = None,
    action_phrase: str | None = None,
) -> ActivityFrame | None:
    name = (label or "").strip()
    if not name:
        return None
    obj = (object_phrase or "").strip() or None
    if obj == name:
        obj = None
    action = (action_phrase or "").strip() or None
    mode = "departure" if _is_departure_action(action) else None
    return ActivityFrame(
        label=name,
        object_phrase=obj,
        action_stem=normalize_action_stem(action),
        mode=mode,
    )


def build_activity_frame_from_detail(detail: dict[str, Any]) -> ActivityFrame | None:
    if not isinstance(detail, dict):
        return None
    raw = detail.get("activity_frame")
    if isinstance(raw, dict):
        parsed = activity_frame_from_dict(raw)
        if parsed is not None:
            return parsed
    event = detail.get("event")
    if isinstance(event, dict):
        what = str(event.get("what") or "").strip()
        if what:
            return build_activity_frame_for_open(
                label=what,
                object_phrase=str(detail.get("object_phrase") or "").strip() or None,
                action_phrase=str(event.get("action_phrase") or detail.get("action_phrase") or "").strip()
                or None,
            )
    terms = detail.get("action_terms")
    if isinstance(terms, list):
        for item in terms:
            token = str(item).strip()
            if token:
                return build_activity_frame_for_open(
                    label=token,
                    object_phrase=str(detail.get("object_phrase") or "").strip() or None,
                    action_phrase=str(detail.get("action_phrase") or "").strip() or None,
                )
    return None


def ensure_activity_frame_in_detail(detail: dict[str, Any]) -> dict[str, Any]:
    """Attach activity_frame dict when missing (loop create path)."""
    if not isinstance(detail, dict):
        return detail
    if isinstance(detail.get("activity_frame"), dict):
        return detail
    frame = build_activity_frame_from_detail(detail)
    if frame is None:
        return detail
    merged = dict(detail)
    merged["activity_frame"] = activity_frame_to_dict(frame)
    return merged


def build_completion_frame(
    *,
    object_phrase: str | None,
    action_phrase: str | None,
    utterance: str,
    action_terms: tuple[str, ...] | list[str] = (),
) -> ActivityFrame:
    obj = (object_phrase or "").strip() or None
    if not obj:
        for term in action_terms:
            token = str(term).strip()
            if token:
                obj = token
                break
    label = obj or (utterance.strip()[:40] or "activity")
    return ActivityFrame(
        label=label,
        object_phrase=obj,
        action_stem=normalize_action_stem(action_phrase),
        mode="completion",
    )


def _action_present_in_utterance(*, action_stem: str | None, utterance: str) -> bool:
    text = utterance.strip()
    if not text:
        return False
    if action_stem and action_stem in text:
        return True
    raw = (action_stem or "").strip()
    return bool(raw) and raw in text


def activity_label_in_text(label: str, text: str) -> bool:
    lab = (label or "").strip()
    raw = (text or "").strip()
    if not lab or not raw:
        return False
    return lab in raw


def _activity_names_align(
    *,
    loop_frame: ActivityFrame,
    close_frame: ActivityFrame,
    utterance: str,
) -> bool:
    """True when utterance or Stage1 object slot names this loop's activity."""
    text = utterance.strip()
    label = loop_frame.label.strip()
    if label and activity_label_in_text(label, text):
        return True

    obj = (close_frame.object_phrase or close_frame.label or "").strip()
    if len(obj) < 2 or not activity_label_in_text(obj, text):
        return False

    loop_obj = (loop_frame.object_phrase or label).strip()
    if not loop_obj:
        return False
    return obj in loop_obj or loop_obj in obj or obj in label or label in obj


def frames_match_completion(
    loop_frame: ActivityFrame,
    close_frame: ActivityFrame,
    *,
    utterance: str,
    close_action_phrase: str | None = None,
) -> bool:
    """Pair a Stage1 past_completion utterance with an open loop (which activity).

    Caller must only invoke when ``utterance_kind=past_completion`` — completion
    truth comes from e4b Stage1, not from verb lists in this module.
    """
    _ = close_action_phrase  # stem fallback only; completion gate is Stage1
    text = utterance.strip()
    if not text:
        return False

    if not _activity_names_align(loop_frame=loop_frame, close_frame=close_frame, utterance=text):
        loop_obj = (loop_frame.object_phrase or "").strip()
        obj = (close_frame.object_phrase or close_frame.label or "").strip()
        if not (loop_obj and obj and loop_obj == obj):
            return False

    # Departure loop + activity named → close (してきた / 終わった 等は Stage1 が past_completion)
    if loop_frame.mode == "departure" and _activity_names_align(
        loop_frame=loop_frame,
        close_frame=close_frame,
        utterance=text,
    ):
        return True

    if _activity_names_align(loop_frame=loop_frame, close_frame=close_frame, utterance=text):
        return _action_present_in_utterance(action_stem=close_frame.action_stem, utterance=text)

    loop_obj = (loop_frame.object_phrase or "").strip()
    obj = (close_frame.object_phrase or close_frame.label or "").strip()
    if loop_obj and obj and loop_obj == obj:
        if close_frame.action_stem and loop_frame.action_stem:
            if close_frame.action_stem[:1] == loop_frame.action_stem[:1]:
                return _action_present_in_utterance(
                    action_stem=close_frame.action_stem,
                    utterance=text,
                )
        return _action_present_in_utterance(action_stem=close_frame.action_stem, utterance=text)

    return False


def is_unscoped_past_completion(
    *,
    utterance_kind: str | None,
    object_phrase: str | None,
    action_phrase: str | None,
) -> bool:
    """Legacy fallback when close_shape omitted — object null + action present."""
    if utterance_kind != "past_completion":
        return False
    if (object_phrase or "").strip():
        return False
    return bool((action_phrase or "").strip())


def is_action_only_close(
    *,
    utterance_kind: str | None,
    close_shape: str | None,
    object_phrase: str | None,
    action_phrase: str | None,
) -> bool:
    """Stage1 past_completion with action-only close (終わった / 行ってきた / ただいま 等)."""
    if utterance_kind != "past_completion":
        return False
    if close_shape == "activity_named":
        return False
    if close_shape == "action_only":
        return bool((action_phrase or "").strip())
    return is_unscoped_past_completion(
        utterance_kind=utterance_kind,
        object_phrase=object_phrase,
        action_phrase=action_phrase,
    )
