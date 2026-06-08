#!/usr/bin/env python3
"""Test Tapo capture without MCP. Run from wifi-cam-mcp/:

  uv run python scripts/test_capture.py

Requires TAPO_CAMERA_HOST, TAPO_USERNAME, TAPO_PASSWORD in the environment.
"""
from __future__ import annotations

import asyncio
import os
import sys


async def main() -> int:
    host = os.environ.get("TAPO_CAMERA_HOST", "")
    user = os.environ.get("TAPO_USERNAME", "")
    if not host or not user or not os.environ.get("TAPO_PASSWORD"):
        print("Set TAPO_CAMERA_HOST, TAPO_USERNAME, TAPO_PASSWORD", file=sys.stderr)
        return 1

    from wifi_cam_mcp.camera import TapoCamera
    from wifi_cam_mcp.config import CameraConfig

    config = CameraConfig.from_env()
    cam = TapoCamera(config, capture_dir=os.environ.get("CAPTURE_DIR", ""))
    print(f"Connecting to {config.host} ...")
    await cam.connect()
    try:
        result = await cam.capture_image()
        path = getattr(result, "file_path", None) or getattr(result, "path", "")
        print(f"OK {result.width}x{result.height} base64_len={len(result.image_base64)}")
        if path:
            print(f"saved: {path}")
    finally:
        await cam.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
