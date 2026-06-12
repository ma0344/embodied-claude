#!/usr/bin/env python3
"""SessionStart (startup/resume): remind the agent to read SOUL.md."""

from __future__ import annotations

import sys
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from hook_io import ensure_utf8_stdio  # noqa: E402


def main() -> int:
    ensure_utf8_stdio()
    soul = Path(__file__).resolve().parents[2] / "SOUL.md"
    if soul.is_file():
        sys.stdout.write(
            "[session_start] SOUL.md がある。会話を始める前に Read で SOUL.md を読むか /soul を実行。\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
