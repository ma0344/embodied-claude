#!/usr/bin/env python3
"""Capture one frame and run LM Studio vision describe (same path as MCP see).

  cd wifi-cam-mcp
  # Option A: wifi-cam-mcp/.env (copy from .env.example)
  # Option B: same TAPO_* / ANTHROPIC_* as project .mcp.json wifi-cam env
  uv run python scripts/test_vision_describe.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PKG_ROOT / "src"))


def _load_env() -> None:
    """Load wifi-cam-mcp/.env then repo-root .env if present."""
    load_dotenv(_PKG_ROOT / ".env")
    repo_root = _PKG_ROOT.parent
    load_dotenv(repo_root / ".env")


def _missing_tapo_env() -> list[str]:
    need = ("TAPO_CAMERA_HOST", "TAPO_USERNAME", "TAPO_PASSWORD")
    return [k for k in need if not (os.environ.get(k) or "").strip()]


async def main() -> int:
    _load_env()

    from wifi_cam_mcp.camera import TapoCamera
    from wifi_cam_mcp.config import CameraConfig
    from wifi_cam_mcp.server import _describe_image_via_lm_studio, _lm_studio_settings

    missing = _missing_tapo_env()
    if missing:
        print("Missing camera env (set in wifi-cam-mcp/.env or PowerShell):", file=sys.stderr)
        for k in missing:
            print(f"  - {k}", file=sys.stderr)
        print(
            f"\nExample: copy {_PKG_ROOT / '.env.example'} -> {_PKG_ROOT / '.env'}",
            file=sys.stderr,
        )
        print("Or match values from embodied-claude/.mcp.json → mcpServers.wifi-cam.env", file=sys.stderr)
        return 1

    base, model, _token = _lm_studio_settings()
    print(f"LM Studio: {base} model={model}")

    cam = TapoCamera(CameraConfig.from_env())
    await cam.connect()
    try:
        cap = await cam.capture_image()
        print(f"capture OK {cap.width}x{cap.height} -> {cap.file_path}")
        caption = await _describe_image_via_lm_studio(cap.image_base64)
        if caption:
            print("\n=== VISION_CAPTION ===")
            print(caption)
            return 0
        print("\nVISION_DESCRIBE_FAILED (check LM Studio model is vision-capable & loaded)", file=sys.stderr)
        return 2
    finally:
        await cam.disconnect()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
