"""Shared noise stripping for private reflection / inner-voice text."""

from __future__ import annotations

import re

_INJECTION_RE = re.compile(
    r"\[(?:gateway_turn_context|stm_recent|dream_digest|interaction_context)\b",
    re.I,
)


def strip_reflection_noise(text: str) -> str:
    lines: list[str] = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _INJECTION_RE.search(stripped):
            continue
        if stripped.startswith("Autonomous tick"):
            continue
        if stripped.startswith("Open loops:"):
            continue
        if stripped.startswith("Calendar today"):
            continue
        if stripped.startswith("[desires]") or stripped.startswith("[/desires]"):
            continue
        if "Dominant pull:" in stripped and "Open loops:" in stripped:
            continue
        if stripped.startswith("（自律の思考メモ）"):
            stripped = stripped.removeprefix("（自律の思考メモ）").strip()
        lines.append(stripped)
    return "\n".join(lines).strip()
