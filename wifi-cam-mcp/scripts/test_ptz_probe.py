#!/usr/bin/env python3
"""PTZ probe for Tapo ONVIF (CAM-1 / TP-Link FAQ Q14 style).

Compares hardware GetStatus + JPEG before/after pan moves.
Run from wifi-cam-mcp/:

  uv run python scripts/test_ptz_probe.py
  uv run python scripts/test_ptz_probe.py --mode continuous

Requires TAPO_CAMERA_HOST, TAPO_USERNAME, TAPO_PASSWORD in .env or env.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import os
import sys
from pathlib import Path

# Load .env when present (local dev)
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass


def _jpeg_hash(capture) -> str:
    raw = base64.b64decode(capture.image_base64)
    return hashlib.sha256(raw).hexdigest()[:16]


def _pos_label(pos) -> str:
    if pos is None:
        return "none"
    return f"pan={pos.pan:.4f} tilt={pos.tilt:.4f}"


async def main() -> int:
    parser = argparse.ArgumentParser(description="Tapo ONVIF PTZ probe")
    parser.add_argument(
        "--mode",
        choices=("auto", "relative", "continuous"),
        default=os.environ.get("TAPO_PTZ_MODE", "auto"),
        help="PTZ mode override for this run",
    )
    parser.add_argument("--degrees", type=int, default=30, help="Pan degrees per step")
    args = parser.parse_args()

    host = os.environ.get("TAPO_CAMERA_HOST", "")
    user = os.environ.get("TAPO_USERNAME", "")
    if not host or not user or not os.environ.get("TAPO_PASSWORD"):
        print("Set TAPO_CAMERA_HOST, TAPO_USERNAME, TAPO_PASSWORD", file=sys.stderr)
        return 1

    os.environ["TAPO_PTZ_MODE"] = args.mode

    from wifi_cam_mcp.camera import TapoCamera
    from wifi_cam_mcp.config import CameraConfig

    config = CameraConfig.from_env()
    cam = TapoCamera(config, capture_dir=os.environ.get("CAPTURE_DIR", ""))

    print(f"=== Tapo PTZ probe (mode={args.mode}) ===")
    print(f"host={config.host} onvif_port={config.onvif_port}")

    await cam.connect()
    try:
        info = await cam.get_device_info()
        model = info.get("Model") or info.get("model") or "?"
        fw = info.get("FirmwareVersion") or info.get("firmware") or "?"
        print(f"device: {model} fw={fw}")

        presets = await cam.get_presets()
        print(f"presets: {len(presets)}")
        for p in presets[:5]:
            print(f"  - {p}")

        hw0 = await cam.get_hw_position()
        sw0 = cam.get_position()
        cap0 = await cam.capture_image(save_to_file=False)
        h0 = _jpeg_hash(cap0)
        print(f"\n[baseline] hw={_pos_label(hw0)} sw={_pos_label(sw0)} jpeg={h0}")

        move = await cam.pan_left(args.degrees)
        print(f"pan_left({args.degrees}): success={move.success} msg={move.message}")

        await asyncio.sleep(1.0)
        hw1 = await cam.get_hw_position()
        sw1 = cam.get_position()
        cap1 = await cam.capture_image(save_to_file=False)
        h1 = _jpeg_hash(cap1)
        print(f"[after left] hw={_pos_label(hw1)} sw={_pos_label(sw1)} jpeg={h1}")

        move2 = await cam.pan_right(args.degrees)
        print(f"pan_right({args.degrees}): success={move2.success} msg={move2.message}")

        await asyncio.sleep(1.0)
        hw2 = await cam.get_hw_position()
        cap2 = await cam.capture_image(save_to_file=False)
        h2 = _jpeg_hash(cap2)
        print(f"[after right] hw={_pos_label(hw2)} jpeg={h2}")

        hw_moved = (
            hw0 is not None
            and hw1 is not None
            and (abs(hw1.pan - hw0.pan) > 0.01 or abs(hw1.tilt - hw0.tilt) > 0.01)
        )
        jpeg_moved = h0 != h1

        print("\n=== summary ===")
        print(f"ONVIF GetStatus changed after pan_left: {hw_moved}")
        print(f"JPEG hash changed after pan_left: {jpeg_moved}")
        if move.success and not hw_moved and not jpeg_moved:
            print(
                "LIKELY: RelativeMove returns OK but camera did not move "
                "(FAQ Q14 — try another client or continuous mode)"
            )
        elif hw_moved or jpeg_moved:
            print("Direct ONVIF PTZ appears to work on this path.")
        else:
            print(f"Move failed: {move.message}")

        return 0 if (hw_moved or jpeg_moved) else 2
    finally:
        await cam.disconnect()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
