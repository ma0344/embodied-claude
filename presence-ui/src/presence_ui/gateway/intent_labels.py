"""C12 / IBF-7 intent label taxonomy (shared with benchmarks)."""

from __future__ import annotations

ALL_LABELS: frozenset[str] = frozenset(
    {
        "chat",
        "speech",
        "remember",
        "observe_current",
        "observe_window",
        "observe_desk",
        "observe_dining",
        "observe_look_around",
        "ptz_left",
        "ptz_right",
        "ptz_up",
        "ptz_down",
    }
)

BODY_LABELS: frozenset[str] = ALL_LABELS - {"chat"}

LLM_INTENT_SYSTEM_PROMPT = """You classify まー's short Japanese utterance for a home robot gateway.
Return ONLY one JSON object, no markdown:
{"labels": ["..."], "confidence": 0.0}

Rules:
- labels is a sorted list of 1-3 tokens from this set only:
  chat, speech, remember,
  observe_current, observe_window, observe_desk, observe_dining, observe_look_around,
  ptz_left, ptz_right, ptz_up, ptz_down
- Use chat when no body action is requested (greeting, question, chat).
- speech: voice / say / 喋って / 声で
- remember: 覚えて / 記憶して (save new fact). NOT recall questions.
- observe_*: user wants camera vision (見て, どう見える, desk/window/dining/room scan).
- ptz_*: pan/tilt only (左向いて, look left) without needing a scene description reply.
- confidence: 0-1 how sure you are.
"""


def normalize_intent_labels(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        label = str(item).strip()
        if label in ALL_LABELS and label not in out:
            out.append(label)
    body = [label for label in out if label != "chat"]
    if body:
        return sorted(body)
    return sorted(out) if out else ["chat"]
