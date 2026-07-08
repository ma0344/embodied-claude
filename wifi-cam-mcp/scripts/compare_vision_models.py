#!/usr/bin/env python3
"""VIS-e4b POC — same JPEG, same prompt, compare vision models (Qwen vs e4b).

Usage:
  cd wifi-cam-mcp
  uv run python scripts/compare_vision_models.py --capture
  uv run python scripts/compare_vision_models.py --preset window
  uv run python scripts/compare_vision_models.py --image C:\\path\\to\\frame.jpg \\
      --models qwen/qwen2.5-vl-3b-instruct,google/gemma-4-e4b-qat

Env (same as production /see):
  WIFI_CAM_VISION_PROMPT, LM_STUDIO_BASE_URL, ANTHROPIC_AUTH_TOKEN
  TAPO_* when using --capture
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

_PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PKG_ROOT / "src"))

_LOCAL_ENV_CANDIDATES = (
    Path.home() / ".config" / "embodied-claude" / "presence-ui.local.env",
    _PKG_ROOT.parent / "presence-ui" / "presence-ui.local.env",
)


def _ensure_tapo_presets() -> None:
    """Doc defaults for ma-home when env unset (Tapo app preset tokens 1/2/3)."""
    pairs = (
        ("TAPO_MADESK_PRESET", "PRESENCE_CAMERA_DESK_PRESET", "2"),
        ("TAPO_DINING_PRESET", "PRESENCE_CAMERA_DINING_PRESET", "3"),
    )
    for tapo_key, presence_key, default in pairs:
        if os.environ.get(tapo_key, "").strip() or os.environ.get(presence_key, "").strip():
            continue
        os.environ[tapo_key] = default
        print(
            f"Note: {tapo_key} unset — using ma-home doc default {default!r}",
            file=sys.stderr,
        )


def _load_env() -> None:
    load_dotenv(_PKG_ROOT / ".env")
    load_dotenv(_PKG_ROOT.parent / ".env")
    for local in _LOCAL_ENV_CANDIDATES:
        if local.is_file():
            load_dotenv(local)
            break
    _load_mcp_wifi_cam_env()
    _ensure_vision_prompt()
    _ensure_tapo_presets()
    if not os.environ.get("CAPTURE_DIR", "").strip():
        import tempfile

        os.environ["CAPTURE_DIR"] = str(Path(tempfile.gettempdir()) / "wifi-cam-mcp")


def _ensure_vision_prompt() -> None:
    from wifi_cam_mcp.vision import DEFAULT_WIFI_CAM_VISION_PROMPT

    if not os.environ.get("WIFI_CAM_VISION_PROMPT", "").strip():
        os.environ["WIFI_CAM_VISION_PROMPT"] = DEFAULT_WIFI_CAM_VISION_PROMPT
        print(
            "Note: WIFI_CAM_VISION_PROMPT unset — using production default "
            f"({len(DEFAULT_WIFI_CAM_VISION_PROMPT)} chars). "
            "Set in ~/.config/embodied-claude/presence-ui.local.env to match ma-home.",
            file=sys.stderr,
        )


def _load_mcp_wifi_cam_env() -> None:
    """Same TAPO / vision env as Claude Code wifi-cam MCP (.mcp.json)."""
    mcp_path = _PKG_ROOT.parent / ".mcp.json"
    if not mcp_path.is_file():
        return
    try:
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    wenv = (data.get("mcpServers") or {}).get("wifi-cam", {}).get("env") or {}
    if not isinstance(wenv, dict):
        return
    keys = (
        "TAPO_CAMERA_HOST",
        "TAPO_USERNAME",
        "TAPO_PASSWORD",
        "TAPO_ONVIF_PORT",
        "TAPO_STREAM_URL",
        "TAPO_PTZ_MODE",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_AUTH_TOKEN",
        "LM_STUDIO_VISION_MODEL",
        "WIFI_CAM_VISION_PROMPT",
        "WIFI_CAM_VISION_DESCRIBE",
        "WIFI_CAM_VISION_MAX_SIDE",
        "WIFI_CAM_VISION_MAX_TOKENS",
        "CAPTURE_DIR",
        "TAPO_WINDOW_PRESET",
        "TAPO_LOOK_OUTSIDE_PRESET",
        "PRESENCE_CAMERA_WINDOW_PRESET",
        "TAPO_MADESK_PRESET",
        "TAPO_MA_DESK_PRESET",
        "PRESENCE_CAMERA_DESK_PRESET",
        "TAPO_DINING_PRESET",
        "PRESENCE_CAMERA_DINING_PRESET",
        "PRESENCE_CAMERA_PRESET_SETTLE_SEC",
        "PRESENCE_USB_CAMERA_ENABLED",
        "USB_CAMERA_INDEX",
    )
    for key in keys:
        raw = wenv.get(key)
        if raw is not None and str(raw).strip():
            os.environ[key] = str(raw)


def _read_image_b64(path: Path) -> str:
    return base64.standard_b64encode(path.read_bytes()).decode("utf-8")


def _default_models() -> list[str]:
    qwen = os.environ.get("VIS_POC_QWEN_MODEL", "").strip()
    e4b = os.environ.get("VIS_POC_E4B_MODEL", "google/gemma-4-e4b-qat").strip()
    if not qwen:
        qwen = os.environ.get("LM_STUDIO_VISION_MODEL", "qwen/qwen2.5-vl-3b-instruct").strip()
    return [m for m in (qwen, e4b) if m]


def _find_latest_capture() -> Path:
    from wifi_cam_mcp.capture_cache import resolve_capture_dir

    root = resolve_capture_dir()
    if not root.is_dir():
        raise SystemExit(
            f"No capture dir {root}. Use --capture (Tapo) or --image PATH."
        )
    files = sorted(
        root.glob("capture_*.jpg"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not files:
        raise SystemExit(
            f"No capture_*.jpg under {root}. Run /see once or use --image PATH."
        )
    return files[0]


_PRESET_ENV_KEYS: dict[str, tuple[str, ...]] = {
    "window": (
        "PRESENCE_CAMERA_WINDOW_PRESET",
        "TAPO_WINDOW_PRESET",
        "TAPO_LOOK_OUTSIDE_PRESET",
    ),
    "desk": (
        "PRESENCE_CAMERA_DESK_PRESET",
        "TAPO_MADESK_PRESET",
        "TAPO_MA_DESK_PRESET",
    ),
    "dining": (
        "PRESENCE_CAMERA_DINING_PRESET",
        "TAPO_DINING_PRESET",
    ),
}


def _resolve_preset_id(preset: str) -> str | None:
    for key in _PRESET_ENV_KEYS.get(preset, ()):
        raw = os.environ.get(key, "").strip()
        if raw:
            return raw
    return None


async def _capture_preset_b64(preset: str) -> tuple[str, str]:
    import asyncio as aio

    from wifi_cam_mcp.camera import TapoCamera
    from wifi_cam_mcp.config import CameraConfig

    preset = preset.strip().lower()
    if preset not in _PRESET_ENV_KEYS:
        raise SystemExit(
            f"Unknown --preset {preset!r}. Use: {', '.join(_PRESET_ENV_KEYS)}"
        )

    if preset == "window" and os.environ.get("PRESENCE_USB_CAMERA_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        raise SystemExit(
            "USB outside camera is enabled — use gateway smoke look_outside JPEG + --image:\n"
            "  Invoke-RestMethod .../autonomous-tick -Body "
            '\'{"smoke_action":"look_outside","trigger":"smoke"}\''
        )

    preset_id = _resolve_preset_id(preset)
    if not preset_id:
        keys = ", ".join(_PRESET_ENV_KEYS[preset])
        raise SystemExit(
            f"{preset} preset not configured. Set one of: {keys} "
            "in ~/.config/embodied-claude/presence-ui.local.env"
        )

    missing = [
        k
        for k in ("TAPO_CAMERA_HOST", "TAPO_USERNAME", "TAPO_PASSWORD")
        if not (os.environ.get(k) or "").strip()
    ]
    if missing:
        raise SystemExit(f"Missing camera env: {', '.join(missing)}")

    cam = TapoCamera(CameraConfig.from_env())
    try:
        await cam.connect()
    except Exception as exc:
        raise SystemExit(f"ONVIF connect failed: {exc}") from exc
    try:
        move = await cam.go_to_preset(preset_id)
        if not move.success:
            raise SystemExit(f"go_to_preset({preset_id}) failed: {move.message}")
        await aio.sleep(float(os.environ.get("PRESENCE_CAMERA_PRESET_SETTLE_SEC", "2.5")))
        cap = await cam.capture_image()
        path = cap.file_path or f"(preset {preset_id})"
        return cap.image_base64, path
    finally:
        await cam.disconnect()


async def _capture_b64() -> tuple[str, str]:
    from wifi_cam_mcp.camera import TapoCamera
    from wifi_cam_mcp.config import CameraConfig

    missing = [
        k
        for k in ("TAPO_CAMERA_HOST", "TAPO_USERNAME", "TAPO_PASSWORD")
        if not (os.environ.get(k) or "").strip()
    ]
    if missing:
        raise SystemExit(
            f"Missing camera env: {', '.join(missing)} "
            "(check wifi-cam-mcp/.env or .mcp.json → mcpServers.wifi-cam.env)"
        )

    cam = TapoCamera(CameraConfig.from_env())
    try:
        await cam.connect()
    except Exception as exc:
        host = os.environ.get("TAPO_CAMERA_HOST", "?")
        port = os.environ.get("TAPO_ONVIF_PORT", "2020")
        msg = str(exc)
        hint = (
            f"ONVIF connect failed ({host}:{port}): {msg}\n"
            "Hints:\n"
            "  - Use production creds from .mcp.json (script loads them automatically)\n"
            "  - Tapo: local camera account (not TP-Link cloud), fixed IP\n"
            "  - Try --latest or --image PATH to skip live capture\n"
        )
        if "Authority" in msg:
            hint += "  - Authority failure = wrong username/password or ONVIF port\n"
        raise SystemExit(hint) from exc
    try:
        cap = await cam.capture_image()
        path = cap.file_path or "(memory)"
        return cap.image_base64, path
    finally:
        await cam.disconnect()


async def _describe_one(
    model: str,
    image_b64: str,
    *,
    isolate: bool = False,
    peer_models: list[str] | None = None,
) -> dict[str, object]:
    import httpx

    from wifi_cam_mcp.lm_studio_models import prepare_isolated_vision_model
    from wifi_cam_mcp.vision import (
        caption_looks_corrupt,
        describe_image_with_model,
        lm_studio_settings,
        vision_prompt_parts,
        vision_use_system_prompt,
    )

    base, _, token = lm_studio_settings()
    system_prompt, user_text = vision_prompt_parts()
    prompt_label = system_prompt if vision_use_system_prompt() and system_prompt else user_text
    if isolate:
        async with httpx.AsyncClient(timeout=120.0) as client:
            ok = await prepare_isolated_vision_model(
                client,
                base=base,
                token=token,
                model_id=model,
                other_model_ids=peer_models,
            )
            if not ok:
                print(f"Warning: isolate reload failed for {model}", file=sys.stderr)

    outcome = await describe_image_with_model(image_b64, model=model)
    caption = outcome.caption or ""
    corrupt = caption_looks_corrupt(caption) if caption else outcome.saw_corrupt
    return {
        "model": model,
        "base_url": base,
        "system_prompt": bool(system_prompt and vision_use_system_prompt()),
        "prompt_chars": len(prompt_label or ""),
        "prompt_preview": (prompt_label or "")[:80],
        "caption": caption,
        "caption_chars": len(caption),
        "corrupt": corrupt,
        "saw_corrupt_raw": outcome.saw_corrupt,
        "reloaded": outcome.reloaded,
        "finish_reason": outcome.finish_reason,
        "api_route": outcome.api_route,
        "ok": bool(caption and not corrupt),
    }


def _print_report(
    *,
    image_source: str,
    results: list[dict[str, object]],
    out_path: Path | None,
    isolate: bool,
) -> None:
    system_mode = results[0].get("system_prompt", False) if results else False
    lines = [
        f"# VIS-e4b POC - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"- **image**: `{image_source}`",
        f"- **prompt**: `WIFI_CAM_VISION_PROMPT` → "
        f"{'system' if system_mode else 'user'} ({results[0].get('prompt_chars', '?')} chars)",
        f"- **prompt preview**: `{results[0].get('prompt_preview', '')}`",
        f"- **isolate**: `{isolate}` (unload peers + reload each model before describe)",
        "",
        "| model | chars | finish | api | corrupt | ok |",
        "|-------|------:|--------|-----|---------|-----|",
    ]
    for row in results:
        finish = row.get("finish_reason") or "—"
        api = row.get("api_route") or "—"
        if isinstance(api, str) and api.startswith("/v1/"):
            api = api.removeprefix("/v1/")
        lines.append(
            f"| `{row['model']}` | {row['caption_chars']} | {finish} | {api} | "
            f"{'yes' if row['corrupt'] else 'no'} | {'✅' if row['ok'] else '❌'} |"
        )
    lines.append("")
    for row in results:
        lines.extend(
            [
                f"## {row['model']}",
                "",
                "```",
                str(row["caption"] or "(empty / failed)"),
                "```",
                "",
            ]
        )
    text = "\n".join(lines)
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"Wrote {out_path}", file=sys.stderr)
    try:
        reconfigure = getattr(sys.stdout, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")
        print(text)
    except UnicodeEncodeError:
        print(text.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))


async def main() -> int:
    _load_env()
    parser = argparse.ArgumentParser(description="Compare LM Studio vision models on one JPEG")
    parser.add_argument("--capture", action="store_true", help="Capture one Tapo frame first")
    parser.add_argument(
        "--preset",
        choices=tuple(_PRESET_ENV_KEYS),
        help="Move to Tapo preset before capture (window / desk / dining)",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Use newest capture_*.jpg from CAPTURE_DIR",
    )
    parser.add_argument("--image", type=Path, help="Existing JPEG path")
    parser.add_argument(
        "--models",
        default="",
        help="Comma-separated model ids (default: LM_STUDIO_VISION_MODEL + google/gemma-4-e4b-qat)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write markdown report (default: benchmarks/vis-e4b-poc-<date>.md under repo root)",
    )
    parser.add_argument(
        "--out-suffix",
        default="",
        help="Append to default report filename (e.g. usb-outside)",
    )
    parser.add_argument(
        "--isolate",
        action="store_true",
        help="Unload other models and reload each target before describe (fair A/B)",
    )
    parser.add_argument("--json", action="store_true", help="Also print JSON to stdout")
    args = parser.parse_args()

    if args.capture:
        image_b64, image_source = await _capture_b64()
    elif args.preset:
        image_b64, image_source = await _capture_preset_b64(args.preset)
    elif args.latest:
        latest = _find_latest_capture()
        image_b64 = _read_image_b64(latest)
        image_source = str(latest)
    elif args.image:
        if not args.image.is_file():
            raise SystemExit(f"Image not found: {args.image}")
        image_b64 = _read_image_b64(args.image)
        image_source = str(args.image)
    else:
        parser.error("Use --capture, --preset window, --latest, or --image")

    models = [m.strip() for m in args.models.split(",") if m.strip()] or _default_models()
    if len(models) < 2:
        print("Warning: only one model — add --models qwen-id,e4b-id", file=sys.stderr)

    results: list[dict[str, object]] = []
    for model in models:
        print(f"Describing with {model}...", file=sys.stderr)
        results.append(
            await _describe_one(
                model,
                image_b64,
                isolate=args.isolate,
                peer_models=[m for m in models if m != model],
            )
        )

    out_path = args.out
    if out_path is None:
        stamp = datetime.now().strftime("%Y-%m-%d")
        suffix = ""
        if args.preset:
            suffix = f"-{args.preset}"
        if args.out_suffix:
            suffix = f"{suffix}-{args.out_suffix}" if suffix else f"-{args.out_suffix}"
        out_path = _PKG_ROOT.parent / "benchmarks" / f"vis-e4b-poc-{stamp}{suffix}.md"

    _print_report(
        image_source=image_source,
        results=results,
        out_path=out_path,
        isolate=args.isolate,
    )
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if all(r["ok"] for r in results) else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
