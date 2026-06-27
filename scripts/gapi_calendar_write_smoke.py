#!/usr/bin/env python3
"""Thin wrapper — run from repo root: uv run python scripts/gapi_calendar_write_smoke.py"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    presence = repo / "presence-ui"
    return subprocess.call(
        ["uv", "run", "gapi-calendar-write-smoke", *sys.argv[1:]],
        cwd=presence,
    )


if __name__ == "__main__":
    raise SystemExit(main())
