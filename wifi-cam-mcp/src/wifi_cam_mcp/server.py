"""MCP Server for WiFi Camera Control - Let AI see the world!"""

import asyncio
import base64
import io
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    ImageContent,
    TextContent,
    Tool,
)

from ._behavior import get_behavior
from .camera import CaptureResult, TapoCamera
from .config import CameraConfig, ServerConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _text_only_tool_results() -> bool:
    """LM Studio /v1/messages rejects image blocks inside tool_result arrays."""
    raw = os.environ.get("WIFI_CAM_TEXT_ONLY_TOOL_RESULT", "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    if not raw and sys.platform == "win32":
        return True
    return bool(get_behavior("wifi-cam", "text_only_tool_result", False))


def _vision_describe_enabled() -> bool:
    raw = os.environ.get("WIFI_CAM_VISION_DESCRIBE", "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    return _text_only_tool_results()


def _lm_studio_settings() -> tuple[str, str, str]:
    base = (
        os.environ.get("LM_STUDIO_BASE_URL")
        or os.environ.get("ANTHROPIC_BASE_URL")
        or "http://127.0.0.1:1234"
    ).rstrip("/")
    model = (
        os.environ.get("LM_STUDIO_VISION_MODEL")
        or os.environ.get("CLAUDE_MODEL")
        or "google/gemma-4-12b-qat"
    )
    token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()
    if not token:
        token_file = os.environ.get(
            "LM_STUDIO_TOKEN_FILE",
            str(Path.home() / ".config" / "embodied-claude" / "lmstudio.token"),
        )
        if Path(token_file).is_file():
            token = Path(token_file).read_text(encoding="utf-8").strip()
    if not token:
        token = "lmstudio"
    return base, model, token


def _resize_image_base64(image_base64: str, max_side: int = 768) -> str:
    """Shrink image for vision API (faster, fewer LM Studio failures)."""
    raw = base64.standard_b64decode(image_base64)
    img = Image.open(io.BytesIO(raw))
    img.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")


def _lm_auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "x-api-key": token,
        "Content-Type": "application/json",
    }


def _parse_openai_chat_content(data: dict) -> str | None:
    choices = data.get("choices") or []
    if not choices:
        return None
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        joined = "\n".join(p for p in parts if p).strip()
        return joined or None
    return None


def _parse_anthropic_message_content(data: dict) -> str | None:
    content = (data.get("content") or []) if isinstance(data, dict) else []
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text", "")
            if text and str(text).strip():
                parts.append(str(text).strip())
    return "\n".join(parts).strip() or None


async def _describe_via_chat(
    client: httpx.AsyncClient,
    base: str,
    model: str,
    headers: dict[str, str],
    prompt: str,
    image_b64: str,
) -> str | None:
    url = f"{base}/v1/chat/completions"
    payload = {
        "model": model,
        "max_tokens": 600,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                    },
                ],
            }
        ],
    }
    resp = await client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    return _parse_openai_chat_content(resp.json())


async def _describe_via_messages(
    client: httpx.AsyncClient,
    base: str,
    model: str,
    headers: dict[str, str],
    prompt: str,
    image_b64: str,
) -> str | None:
    url = f"{base}/v1/messages"
    payload = {
        "model": model,
        "max_tokens": 600,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64,
                        },
                    },
                ],
            }
        ],
    }
    resp = await client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    return _parse_anthropic_message_content(resp.json())


async def _describe_image_via_lm_studio(image_base64: str) -> str | None:
    """Send JPEG to LM Studio vision; return text-only caption.

    LM Studio の GUI チャットに近いのは OpenAI /v1/chat/completions 側のことが多い。
    Claude Code 本体は /v1/messages だが、ここは MCP からの別リクエストなので形式は選べる。
    """
    base, model, token = _lm_studio_settings()
    max_side = int(os.environ.get("WIFI_CAM_VISION_MAX_SIDE", "1024"))
    prompt = os.environ.get(
        "WIFI_CAM_VISION_PROMPT",
        "この画像を説明して。実際に見えるものだけ。見えないことは書かない。",
    )
    image_b64 = _resize_image_base64(image_base64, max_side=max_side)
    headers = _lm_auth_headers(token)
    api_pref = os.environ.get("WIFI_CAM_VISION_API", "auto").strip().lower()
    if api_pref in ("chat", "openai", "completions"):
        order = ["chat"]
    elif api_pref in ("messages", "anthropic"):
        order = ["messages"]
    else:
        order = ["chat", "messages"]

    async with httpx.AsyncClient(timeout=120.0) as client:
        for kind in order:
            try:
                if kind == "chat":
                    caption = await _describe_via_chat(
                        client, base, model, headers, prompt, image_b64
                    )
                    label = "/v1/chat/completions"
                else:
                    caption = await _describe_via_messages(
                        client, base, model, headers, prompt, image_b64
                    )
                    label = "/v1/messages"
                if caption:
                    logger.info("Vision describe OK via %s (%d chars)", label, len(caption))
                    return caption
                logger.warning("Vision describe %s: empty content", label)
            except Exception as e:
                logger.warning("Vision describe %s failed: %s", kind, e)

    return None


def _format_capture_text(
    result: CaptureResult, label: str = "", *, vision_caption: str | None = None
) -> str:
    lines: list[str] = []
    if label:
        lines.append(label)
    lines.append(
        f"Captured image at {result.timestamp} ({result.width}x{result.height})."
    )
    if result.file_path:
        lines.append(f"file_path: {result.file_path}")
    if vision_caption:
        lines.append("")
        lines.append("=== VISION_CAPTION (唯一の根拠。ここに無い内容を推測で述べない) ===")
        lines.append(vision_caption)
        lines.append("=== END VISION_CAPTION ===")
    elif _text_only_tool_results() and _vision_describe_enabled():
        lines.append("")
        lines.append("=== VISION_DESCRIBE_FAILED ===")
        lines.append(
            "LM Studio への画像説明リクエストが失敗しました。"
            " 部屋の様子・物体を推測で述べないこと。"
            " ユーザーには file_path の JPEG を開いて確認するよう伝えてください。"
        )
        lines.append("=== END VISION_DESCRIBE_FAILED ===")
    return "\n".join(lines)


async def _capture_tool_contents(
    result: CaptureResult, *, label: str = ""
) -> list[TextContent | ImageContent]:
    if _text_only_tool_results():
        vision_caption = None
        if _vision_describe_enabled():
            vision_caption = await _describe_image_via_lm_studio(result.image_base64)
        return [
            TextContent(
                type="text",
                text=_format_capture_text(result, label, vision_caption=vision_caption),
            )
        ]
    items: list[TextContent | ImageContent] = [
        ImageContent(
            type="image",
            data=result.image_base64,
            mimeType="image/jpeg",
        ),
    ]
    short = f"Captured image at {result.timestamp} ({result.width}x{result.height})"
    if label:
        short = f"{label}: {short}"
    items.append(TextContent(type="text", text=short))
    return items


class CameraMCPServer:
    """MCP Server that gives AI eyes to see the room."""

    def __init__(self):
        self._server = Server("wifi-cam-mcp")
        self._camera: TapoCamera | None = None  # Left/primary camera
        self._camera_right: TapoCamera | None = None  # Right camera (optional)
        self._server_config = ServerConfig.from_env()
        self._has_stereo = False
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Set up MCP tool handlers."""

        @self._server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available camera control tools."""
            tools = [
                Tool(
                    name="see",
                    description="See what's in front of you right now (using your eyes/camera). Returns the current view as an image. Use this when someone asks you to look at something or when you want to observe your surroundings.",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="look_left",
                    description="Turn your head/neck to the LEFT to see what's there. Use this when you want to look at something on your left side.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "degrees": {
                                "type": "integer",
                                "description": "How far to turn left (1-90 degrees, default: 30)",
                                "default": 30,
                                "minimum": 1,
                                "maximum": 90,
                            }
                        },
                        "required": [],
                    },
                ),
                Tool(
                    name="look_right",
                    description="Turn your head/neck to the RIGHT to see what's there. Use this when you want to look at something on your right side.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "degrees": {
                                "type": "integer",
                                "description": "How far to turn right (1-90 degrees, default: 30)",
                                "default": 30,
                                "minimum": 1,
                                "maximum": 90,
                            }
                        },
                        "required": [],
                    },
                ),
                Tool(
                    name="look_up",
                    description="Tilt your head UP to see what's above you. Use this when you want to look at the ceiling, sky, or something higher.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "degrees": {
                                "type": "integer",
                                "description": "How far to tilt up (1-90 degrees, default: 20)",
                                "default": 20,
                                "minimum": 1,
                                "maximum": 90,
                            }
                        },
                        "required": [],
                    },
                ),
                Tool(
                    name="look_down",
                    description="Tilt your head DOWN to see what's below you. Use this when you want to look at the floor or something lower.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "degrees": {
                                "type": "integer",
                                "description": "How far to tilt down (1-90 degrees, default: 20)",
                                "default": 20,
                                "minimum": 1,
                                "maximum": 90,
                            }
                        },
                        "required": [],
                    },
                ),
                Tool(
                    name="look_around",
                    description="Look around the room by turning your head to see multiple angles (center, left, right, up). Use this when you want to survey your surroundings or get a full view of the room. Returns multiple images from different angles.",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="camera_info",
                    description="Get information about the camera device.",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="camera_presets",
                    description="List saved camera position presets.",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="camera_go_to_preset",
                    description="Move camera to a saved preset position.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "preset_id": {
                                "type": "string",
                                "description": "The ID of the preset to go to",
                            }
                        },
                        "required": ["preset_id"],
                    },
                ),
                Tool(
                    name="listen",
                    description="Listen with your ears (microphone) to hear what's happening around you. Use this when someone asks 'what do you hear?' or when you want to know what sounds are present. Returns transcribed text of what you heard.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "duration": {
                                "type": "number",
                                "description": "How long to listen in seconds (default: 5, max: 30)",
                                "default": 5,
                                "minimum": 1,
                                "maximum": 30,
                            },
                            "transcribe": {
                                "type": "boolean",
                                "description": "If true, transcribe the audio to text using Whisper (default: true)",
                                "default": True,
                            },
                        },
                        "required": [],
                    },
                ),
            ]

            # Add stereo vision tools if right camera is configured
            if self._has_stereo:
                tools.extend(
                    [
                        Tool(
                            name="see_right",
                            description="See with your RIGHT eye only. Use this when you want to check what the right camera sees specifically.",
                            inputSchema={
                                "type": "object",
                                "properties": {},
                                "required": [],
                            },
                        ),
                        Tool(
                            name="see_both",
                            description="See with BOTH eyes simultaneously (stereo vision). Returns two images side by side - left eye and right eye views. Use this for depth perception or comparing views from both cameras.",
                            inputSchema={
                                "type": "object",
                                "properties": {},
                                "required": [],
                            },
                        ),
                        Tool(
                            name="right_eye_look_left",
                            description="Turn your RIGHT eye to the left.",
                            inputSchema={
                                "type": "object",
                                "properties": {
                                    "degrees": {
                                        "type": "integer",
                                        "description": "How far to turn (1-90 degrees, default: 30)",
                                        "default": 30,
                                        "minimum": 1,
                                        "maximum": 90,
                                    }
                                },
                                "required": [],
                            },
                        ),
                        Tool(
                            name="right_eye_look_right",
                            description="Turn your RIGHT eye to the right.",
                            inputSchema={
                                "type": "object",
                                "properties": {
                                    "degrees": {
                                        "type": "integer",
                                        "description": "How far to turn (1-90 degrees, default: 30)",
                                        "default": 30,
                                        "minimum": 1,
                                        "maximum": 90,
                                    }
                                },
                                "required": [],
                            },
                        ),
                        Tool(
                            name="right_eye_look_up",
                            description="Tilt your RIGHT eye up.",
                            inputSchema={
                                "type": "object",
                                "properties": {
                                    "degrees": {
                                        "type": "integer",
                                        "description": "How far to tilt (1-90 degrees, default: 20)",
                                        "default": 20,
                                        "minimum": 1,
                                        "maximum": 90,
                                    }
                                },
                                "required": [],
                            },
                        ),
                        Tool(
                            name="right_eye_look_down",
                            description="Tilt your RIGHT eye down.",
                            inputSchema={
                                "type": "object",
                                "properties": {
                                    "degrees": {
                                        "type": "integer",
                                        "description": "How far to tilt (1-90 degrees, default: 20)",
                                        "default": 20,
                                        "minimum": 1,
                                        "maximum": 90,
                                    }
                                },
                                "required": [],
                            },
                        ),
                        Tool(
                            name="both_eyes_look_left",
                            description="Turn BOTH eyes to the left together (synchronized head movement).",
                            inputSchema={
                                "type": "object",
                                "properties": {
                                    "degrees": {
                                        "type": "integer",
                                        "description": "How far to turn (1-90 degrees, default: 30)",
                                        "default": 30,
                                        "minimum": 1,
                                        "maximum": 90,
                                    }
                                },
                                "required": [],
                            },
                        ),
                        Tool(
                            name="both_eyes_look_right",
                            description="Turn BOTH eyes to the right together (synchronized head movement).",
                            inputSchema={
                                "type": "object",
                                "properties": {
                                    "degrees": {
                                        "type": "integer",
                                        "description": "How far to turn (1-90 degrees, default: 30)",
                                        "default": 30,
                                        "minimum": 1,
                                        "maximum": 90,
                                    }
                                },
                                "required": [],
                            },
                        ),
                        Tool(
                            name="both_eyes_look_up",
                            description="Tilt BOTH eyes up together (synchronized head movement).",
                            inputSchema={
                                "type": "object",
                                "properties": {
                                    "degrees": {
                                        "type": "integer",
                                        "description": "How far to tilt (1-90 degrees, default: 20)",
                                        "default": 20,
                                        "minimum": 1,
                                        "maximum": 90,
                                    }
                                },
                                "required": [],
                            },
                        ),
                        Tool(
                            name="both_eyes_look_down",
                            description="Tilt BOTH eyes down together (synchronized head movement).",
                            inputSchema={
                                "type": "object",
                                "properties": {
                                    "degrees": {
                                        "type": "integer",
                                        "description": "How far to tilt (1-90 degrees, default: 20)",
                                        "default": 20,
                                        "minimum": 1,
                                        "maximum": 90,
                                    }
                                },
                                "required": [],
                            },
                        ),
                        Tool(
                            name="get_eye_positions",
                            description="Get current position (pan/tilt angles) of both eyes. Use this to check alignment.",
                            inputSchema={
                                "type": "object",
                                "properties": {},
                                "required": [],
                            },
                        ),
                        Tool(
                            name="align_eyes",
                            description="Align both eyes to look at the same direction by adjusting the right eye to match the left eye's position.",
                            inputSchema={
                                "type": "object",
                                "properties": {},
                                "required": [],
                            },
                        ),
                        Tool(
                            name="reset_eye_positions",
                            description="Reset position tracking for both eyes to (0,0). Use this after manually centering the cameras.",
                            inputSchema={
                                "type": "object",
                                "properties": {},
                                "required": [],
                            },
                        ),
                    ]
                )

            return tools

        @self._server.call_tool()
        async def call_tool(
            name: str, arguments: dict[str, Any]
        ) -> list[TextContent | ImageContent]:
            """Handle tool calls."""
            if self._camera is None:
                return [TextContent(type="text", text="Error: Camera not connected")]

            try:
                match name:
                    case "see":
                        result = await self._camera.capture_image()
                        return await _capture_tool_contents(result)

                    case "look_left":
                        degrees = arguments.get("degrees", 30)
                        result = await self._camera.pan_left(degrees)
                        return [TextContent(type="text", text=result.message)]

                    case "look_right":
                        degrees = arguments.get("degrees", 30)
                        result = await self._camera.pan_right(degrees)
                        return [TextContent(type="text", text=result.message)]

                    case "look_up":
                        degrees = arguments.get("degrees", 20)
                        result = await self._camera.tilt_up(degrees)
                        return [TextContent(type="text", text=result.message)]

                    case "look_down":
                        degrees = arguments.get("degrees", 20)
                        result = await self._camera.tilt_down(degrees)
                        return [TextContent(type="text", text=result.message)]

                    case "look_around":
                        captures = await self._camera.look_around()
                        directions = ["Center", "Left", "Right", "Up"]
                        contents: list[TextContent | ImageContent] = []
                        for i, capture in enumerate(captures):
                            direction = directions[i] if i < len(directions) else f"Angle {i}"
                            contents.extend(
                                await _capture_tool_contents(
                                    capture, label=f"--- {direction} View ---"
                                )
                            )
                        contents.append(
                            TextContent(
                                type="text",
                                text=f"Captured {len(captures)} angles. Camera returned to center position.",
                            )
                        )
                        return contents

                    case "camera_info":
                        info = await self._camera.get_device_info()
                        return [
                            TextContent(
                                type="text",
                                text=f"Camera Info:\n{json.dumps(info, indent=2)}",
                            )
                        ]

                    case "camera_presets":
                        presets = await self._camera.get_presets()
                        return [
                            TextContent(
                                type="text",
                                text=f"Camera Presets:\n{json.dumps(presets, indent=2)}",
                            )
                        ]

                    case "camera_go_to_preset":
                        preset_id = arguments.get("preset_id", "")
                        result = await self._camera.go_to_preset(preset_id)
                        return [TextContent(type="text", text=result.message)]

                    case "listen":
                        duration = min(arguments.get("duration", 5), 30)
                        transcribe = arguments.get("transcribe", True)
                        mic_source = get_behavior(
                            "wifi-cam", "mic_source", self._server_config.mic_source
                        )
                        result = await self._camera.listen_audio(
                            duration, transcribe, mic_source
                        )

                        response_text = (
                            f"Recorded {result.duration}s of audio at {result.timestamp}\n"
                        )
                        response_text += f"Audio file: {result.file_path}\n"

                        if result.transcript:
                            response_text += f"\n--- Transcript ---\n{result.transcript}"

                        return [TextContent(type="text", text=response_text)]

                    case "see_right":
                        if not self._camera_right:
                            return [
                                TextContent(type="text", text="Error: Right camera not configured")
                            ]
                        result = await self._camera_right.capture_image()
                        return await _capture_tool_contents(result, label="Right eye")

                    case "see_both":
                        if not self._camera_right:
                            return [
                                TextContent(type="text", text="Error: Right camera not configured")
                            ]

                        # Capture from both cameras concurrently
                        left_task = self._camera.capture_image()
                        right_task = self._camera_right.capture_image()
                        left_result, right_result = await asyncio.gather(left_task, right_task)

                        contents = await _capture_tool_contents(
                            left_result, label="--- Left Eye ---"
                        )
                        contents.extend(
                            await _capture_tool_contents(
                                right_result, label="--- Right Eye ---"
                            )
                        )
                        contents.append(
                            TextContent(
                                type="text",
                                text=(
                                    f"Stereo capture at {left_result.timestamp} "
                                    f"(L: {left_result.width}x{left_result.height}, "
                                    f"R: {right_result.width}x{right_result.height})"
                                ),
                            )
                        )
                        return contents

                    case "right_eye_look_left":
                        if not self._camera_right:
                            return [
                                TextContent(type="text", text="Error: Right camera not configured")
                            ]
                        degrees = arguments.get("degrees", 30)
                        result = await self._camera_right.pan_left(degrees)
                        return [TextContent(type="text", text=f"Right eye: {result.message}")]

                    case "right_eye_look_right":
                        if not self._camera_right:
                            return [
                                TextContent(type="text", text="Error: Right camera not configured")
                            ]
                        degrees = arguments.get("degrees", 30)
                        result = await self._camera_right.pan_right(degrees)
                        return [TextContent(type="text", text=f"Right eye: {result.message}")]

                    case "right_eye_look_up":
                        if not self._camera_right:
                            return [
                                TextContent(type="text", text="Error: Right camera not configured")
                            ]
                        degrees = arguments.get("degrees", 20)
                        result = await self._camera_right.tilt_up(degrees)
                        return [TextContent(type="text", text=f"Right eye: {result.message}")]

                    case "right_eye_look_down":
                        if not self._camera_right:
                            return [
                                TextContent(type="text", text="Error: Right camera not configured")
                            ]
                        degrees = arguments.get("degrees", 20)
                        result = await self._camera_right.tilt_down(degrees)
                        return [TextContent(type="text", text=f"Right eye: {result.message}")]

                    case "both_eyes_look_left":
                        if not self._camera_right:
                            return [
                                TextContent(type="text", text="Error: Right camera not configured")
                            ]
                        degrees = arguments.get("degrees", 30)
                        left_task = self._camera.pan_left(degrees)
                        right_task = self._camera_right.pan_left(degrees)
                        await asyncio.gather(left_task, right_task)
                        return [
                            TextContent(
                                type="text", text=f"Both eyes moved left by {degrees} degrees"
                            )
                        ]

                    case "both_eyes_look_right":
                        if not self._camera_right:
                            return [
                                TextContent(type="text", text="Error: Right camera not configured")
                            ]
                        degrees = arguments.get("degrees", 30)
                        left_task = self._camera.pan_right(degrees)
                        right_task = self._camera_right.pan_right(degrees)
                        await asyncio.gather(left_task, right_task)
                        return [
                            TextContent(
                                type="text", text=f"Both eyes moved right by {degrees} degrees"
                            )
                        ]

                    case "both_eyes_look_up":
                        if not self._camera_right:
                            return [
                                TextContent(type="text", text="Error: Right camera not configured")
                            ]
                        degrees = arguments.get("degrees", 20)
                        left_task = self._camera.tilt_up(degrees)
                        right_task = self._camera_right.tilt_up(degrees)
                        await asyncio.gather(left_task, right_task)
                        return [
                            TextContent(
                                type="text", text=f"Both eyes tilted up by {degrees} degrees"
                            )
                        ]

                    case "both_eyes_look_down":
                        if not self._camera_right:
                            return [
                                TextContent(type="text", text="Error: Right camera not configured")
                            ]
                        degrees = arguments.get("degrees", 20)
                        left_task = self._camera.tilt_down(degrees)
                        right_task = self._camera_right.tilt_down(degrees)
                        await asyncio.gather(left_task, right_task)
                        return [
                            TextContent(
                                type="text", text=f"Both eyes tilted down by {degrees} degrees"
                            )
                        ]

                    case "get_eye_positions":
                        if not self._camera_right:
                            return [
                                TextContent(type="text", text="Error: Right camera not configured")
                            ]
                        left_pos = self._camera.get_position()
                        right_pos = self._camera_right.get_position()
                        return [
                            TextContent(
                                type="text",
                                text=(
                                    f"Left eye:  pan={left_pos.pan:+.0f}deg,"
                                    f" tilt={left_pos.tilt:+.0f}deg\n"
                                    f"Right eye: pan={right_pos.pan:+.0f}deg,"
                                    f" tilt={right_pos.tilt:+.0f}deg\n"
                                    f"Difference:"
                                    f" pan={left_pos.pan - right_pos.pan:+.0f}deg,"
                                    f" tilt={left_pos.tilt - right_pos.tilt:+.0f}deg"
                                ),
                            )
                        ]

                    case "align_eyes":
                        if not self._camera_right:
                            return [
                                TextContent(type="text", text="Error: Right camera not configured")
                            ]
                        left_pos = self._camera.get_position()
                        right_pos = self._camera_right.get_position()

                        pan_diff = left_pos.pan - right_pos.pan
                        tilt_diff = left_pos.tilt - right_pos.tilt

                        messages = []
                        if pan_diff > 0:
                            await self._camera_right.pan_right(pan_diff)
                            messages.append(f"Right eye panned right by {pan_diff}°")
                        elif pan_diff < 0:
                            await self._camera_right.pan_left(-pan_diff)
                            messages.append(f"Right eye panned left by {-pan_diff}°")

                        if tilt_diff > 0:
                            await self._camera_right.tilt_up(tilt_diff)
                            messages.append(f"Right eye tilted up by {tilt_diff}°")
                        elif tilt_diff < 0:
                            await self._camera_right.tilt_down(-tilt_diff)
                            messages.append(f"Right eye tilted down by {-tilt_diff}°")

                        if not messages:
                            return [TextContent(type="text", text="Eyes already aligned!")]

                        return [
                            TextContent(type="text", text="Aligned eyes: " + ", ".join(messages))
                        ]

                    case "reset_eye_positions":
                        if not self._camera_right:
                            return [
                                TextContent(type="text", text="Error: Right camera not configured")
                            ]
                        self._camera.reset_position_tracking()
                        self._camera_right.reset_position_tracking()
                        return [
                            TextContent(
                                type="text", text="Both eyes position tracking reset to (0, 0)"
                            )
                        ]

                    case _:
                        return [TextContent(type="text", text=f"Unknown tool: {name}")]

            except Exception as e:
                logger.exception(f"Error in tool {name}")
                return [TextContent(type="text", text=f"Error: {e!s}")]

    async def connect_camera(self) -> None:
        """Connect to the camera(s)."""
        # Connect primary (left) camera
        config = CameraConfig.from_env()
        self._camera = TapoCamera(config, self._server_config.capture_dir)
        await self._camera.connect()
        logger.info(f"Connected to left/primary camera at {config.host}")

        # Try to connect right camera if configured
        right_config = CameraConfig.right_camera_from_env()
        if right_config:
            try:
                self._camera_right = TapoCamera(right_config, self._server_config.capture_dir)
                await self._camera_right.connect()
                self._has_stereo = True
                logger.info(f"Connected to right camera at {right_config.host} (stereo vision enabled)")
            except Exception as e:
                logger.warning(f"Failed to connect right camera at {right_config.host}: {e}")
                self._camera_right = None
                self._has_stereo = False

    async def disconnect_camera(self) -> None:
        """Disconnect from the camera(s)."""
        if self._camera:
            await self._camera.disconnect()
            self._camera = None
            logger.info("Disconnected from left/primary camera")

        if self._camera_right:
            await self._camera_right.disconnect()
            self._camera_right = None
            self._has_stereo = False
            logger.info("Disconnected from right camera")

    @asynccontextmanager
    async def run_context(self):
        """Context manager for server lifecycle."""
        try:
            await self.connect_camera()
            yield
        finally:
            await self.disconnect_camera()

    async def run(self) -> None:
        """Run the MCP server."""
        async with self.run_context():
            async with stdio_server() as (read_stream, write_stream):
                await self._server.run(
                    read_stream,
                    write_stream,
                    self._server.create_initialization_options(),
                )


def main() -> None:
    """Entry point for the MCP server."""
    try:
        import jurigged
        jurigged.watch(pattern="src/**/*.py", logger=None)
    except ImportError:
        pass
    server = CameraMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
