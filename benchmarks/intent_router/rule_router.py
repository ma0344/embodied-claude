"""Rule-based intent labels — wraps presence-ui ``resolve_user_intent``."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PRESENCE_SRC = _REPO_ROOT / "presence-ui" / "src"
_HOOKS = _REPO_ROOT / ".claude" / "hooks"
for _path in (_PRESENCE_SRC, _HOOKS):
    if _path.is_dir() and str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from presence_ui.gateway.see_intent import detect_ptz_intent, detect_see_intent  # noqa: E402
from presence_ui.gateway.user_intent import resolve_user_intent  # noqa: E402

from taxonomy import ALL_LABELS  # noqa: E402


def classify_with_rules(user_text: str) -> list[str]:
    """Map utterance to canonical label set (sorted)."""
    intent = resolve_user_intent(user_text)
    labels: set[str] = set()

    if intent.wants_speech:
        labels.add("speech")
    if intent.wants_remember:
        labels.add("remember")

    see = detect_see_intent(user_text)
    if see:
        key = f"observe_{see.mode}"
        if key in ALL_LABELS:
            labels.add(key)

    ptz = detect_ptz_intent(user_text)
    if ptz:
        key = f"ptz_{ptz.direction}"
        if key in ALL_LABELS:
            labels.add(key)

    if not labels:
        labels.add("chat")
    return sorted(labels)
