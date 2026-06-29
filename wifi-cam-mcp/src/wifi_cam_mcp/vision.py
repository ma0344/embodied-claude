"""LM Studio vision describe + MCP-compatible capture text (shared with gateway)."""

from __future__ import annotations

import base64
import io
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx
from PIL import Image

from ._behavior import get_behavior
from .camera import CaptureResult

logger = logging.getLogger(__name__)

DEFAULT_WIFI_CAM_VISION_PROMPT = (
    "この部屋の写真。見えているものを具体的に日本語で書いてください。"
    "人物・姿勢・家具・明るさ・窓やモニタの有無。推測や見えないことは書かない。"
    "5〜8文程度。箇条書きや見出しは使わず地の文のみ。"
)


def caption_looks_corrupt(caption: str | None) -> bool:
    """Reject LM Studio outputs that are only replacement question marks."""
    if not caption:
        return False
    stripped = caption.strip()
    if len(stripped) < 4:
        return False
    compact = stripped.replace(" ", "").replace("\n", "")
    if compact and set(compact) <= {"?"}:
        return True
    return stripped.count("?") / len(stripped) > 0.4


def normalize_vision_caption(caption: str | None) -> str | None:
    if caption is None:
        return None
    text = caption.strip()
    if not text:
        return None
    if caption_looks_corrupt(text):
        logger.warning(
            "Vision caption rejected as corrupt (%d chars, mostly '?')",
            len(text),
        )
        return None
    return text


def text_only_tool_results() -> bool:
    """LM Studio /v1/messages rejects image blocks inside tool_result arrays."""
    raw = os.environ.get("WIFI_CAM_TEXT_ONLY_TOOL_RESULT", "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    if not raw and sys.platform == "win32":
        return True
    return bool(get_behavior("wifi-cam", "text_only_tool_result", False))


def vision_describe_enabled() -> bool:
    raw = os.environ.get("WIFI_CAM_VISION_DESCRIBE", "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    return text_only_tool_results()


def lm_studio_settings() -> tuple[str, str, str]:
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


def resize_image_base64(image_base64: str, max_side: int = 768) -> str:
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


def vision_use_system_prompt() -> bool:
    raw = os.environ.get("WIFI_CAM_VISION_USE_SYSTEM", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def vision_prompt_parts() -> tuple[str | None, str]:
    """Split instruction (system) from user turn text — matches LM Studio UI layout."""
    instruction = os.environ.get(
        "WIFI_CAM_VISION_PROMPT",
        DEFAULT_WIFI_CAM_VISION_PROMPT,
    ).strip()
    user_text = os.environ.get(
        "WIFI_CAM_VISION_USER_TEXT",
        "この写真を説明してください。",
    ).strip() or "この写真を説明してください。"
    if vision_use_system_prompt():
        return instruction, user_text
    return None, instruction


def _parse_openai_chat_content(data: dict) -> tuple[str | None, str | None]:
    choices = data.get("choices") or []
    if not choices:
        return None, None
    choice = choices[0]
    finish_reason = choice.get("finish_reason")
    message = choice.get("message") or {}
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip(), finish_reason
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        joined = "\n".join(p for p in parts if p).strip()
        return (joined or None), finish_reason
    return None, finish_reason


def _parse_anthropic_message_content(data: dict) -> tuple[str | None, str | None]:
    stop_reason = data.get("stop_reason") if isinstance(data, dict) else None
    content = (data.get("content") or []) if isinstance(data, dict) else []
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text", "")
            if text and str(text).strip():
                parts.append(str(text).strip())
    joined = "\n".join(parts).strip() or None
    return joined, stop_reason


async def _describe_via_chat(
    client: httpx.AsyncClient,
    base: str,
    model: str,
    headers: dict[str, str],
    system_prompt: str | None,
    user_text: str,
    image_b64: str,
    *,
    max_tokens: int,
) -> tuple[str | None, str | None]:
    url = f"{base}/v1/chat/completions"
    messages: list[dict[str, object]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append(
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                },
            ],
        }
    )
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    resp = await client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    return _parse_openai_chat_content(resp.json())


async def _describe_via_messages(
    client: httpx.AsyncClient,
    base: str,
    model: str,
    headers: dict[str, str],
    system_prompt: str | None,
    user_text: str,
    image_b64: str,
    *,
    max_tokens: int,
) -> tuple[str | None, str | None]:
    url = f"{base}/v1/messages"
    payload: dict[str, object] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
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
    if system_prompt:
        payload["system"] = system_prompt
    resp = await client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    return _parse_anthropic_message_content(resp.json())


@dataclass(slots=True)
class DescribeAttemptResult:
    caption: str | None
    saw_corrupt: bool = False
    finish_reason: str | None = None
    api_route: str | None = None


async def _describe_attempt(
    client: httpx.AsyncClient,
    *,
    base: str,
    model: str,
    headers: dict[str, str],
    system_prompt: str | None,
    user_text: str,
    image_b64: str,
    max_tokens: int,
    api_order: list[str],
) -> DescribeAttemptResult:
    saw_corrupt = False
    for kind in api_order:
        label = "/v1/chat/completions" if kind == "chat" else "/v1/messages"
        try:
            if kind == "chat":
                raw, finish_reason = await _describe_via_chat(
                    client,
                    base,
                    model,
                    headers,
                    system_prompt,
                    user_text,
                    image_b64,
                    max_tokens=max_tokens,
                )
            else:
                raw, finish_reason = await _describe_via_messages(
                    client,
                    base,
                    model,
                    headers,
                    system_prompt,
                    user_text,
                    image_b64,
                    max_tokens=max_tokens,
                )
            if raw and caption_looks_corrupt(raw):
                saw_corrupt = True
                logger.warning(
                    "Vision describe %s returned corrupt caption (%d chars)",
                    label,
                    len(raw),
                )
            caption = normalize_vision_caption(raw)
            if caption:
                logger.info(
                    "Vision describe OK via %s (%d chars, finish=%s)",
                    label,
                    len(caption),
                    finish_reason,
                )
                return DescribeAttemptResult(
                    caption=caption,
                    saw_corrupt=saw_corrupt,
                    finish_reason=finish_reason,
                    api_route=label,
                )
            logger.debug("Vision describe %s: empty or corrupt (finish=%s)", label, finish_reason)
        except Exception as exc:
            logger.warning("Vision describe %s failed: %s", label, exc)
    return DescribeAttemptResult(caption=None, saw_corrupt=saw_corrupt)


@dataclass(slots=True)
class VisionDescribeOutcome:
    caption: str | None
    saw_corrupt: bool = False
    reloaded: bool = False
    finish_reason: str | None = None
    api_route: str | None = None


async def describe_image_outcome(image_base64: str) -> VisionDescribeOutcome:
    """Send JPEG to LM Studio vision; include corrupt/reload metadata."""
    base, model, token = lm_studio_settings()
    return await _describe_image_outcome_for_model(
        image_base64,
        base=base,
        model=model,
        token=token,
    )


async def describe_image_with_model(
    image_base64: str,
    *,
    model: str,
    base: str | None = None,
    token: str | None = None,
) -> VisionDescribeOutcome:
    """Describe using an explicit LM Studio model id (VIS-e4b POC)."""
    resolved_base, _, resolved_token = lm_studio_settings()
    return await _describe_image_outcome_for_model(
        image_base64,
        base=base or resolved_base,
        model=model,
        token=token or resolved_token,
        auto_reload=False,
    )


async def _describe_image_outcome_for_model(
    image_base64: str,
    *,
    base: str,
    model: str,
    token: str,
    auto_reload: bool = True,
) -> VisionDescribeOutcome:
    max_side = int(os.environ.get("WIFI_CAM_VISION_MAX_SIDE", "1024"))
    max_tokens = int(os.environ.get("WIFI_CAM_VISION_MAX_TOKENS", "720"))
    system_prompt, user_text = vision_prompt_parts()
    image_b64 = resize_image_base64(image_base64, max_side=max_side)
    headers = _lm_auth_headers(token)
    api_pref = os.environ.get("WIFI_CAM_VISION_API", "auto").strip().lower()
    if api_pref in ("chat", "openai", "completions"):
        order = ["chat"]
    elif api_pref in ("messages", "anthropic"):
        order = ["messages"]
    else:
        order = ["chat", "messages"]

    saw_corrupt = False
    reloaded = False
    async with httpx.AsyncClient(timeout=120.0) as client:
        attempt = await _describe_attempt(
            client,
            base=base,
            model=model,
            headers=headers,
            system_prompt=system_prompt,
            user_text=user_text,
            image_b64=image_b64,
            max_tokens=max_tokens,
            api_order=order,
        )
        if attempt.caption:
            return VisionDescribeOutcome(
                caption=attempt.caption,
                saw_corrupt=attempt.saw_corrupt,
                finish_reason=attempt.finish_reason,
                api_route=attempt.api_route,
            )
        saw_corrupt = attempt.saw_corrupt

        if saw_corrupt:
            from .lm_studio_models import reload_configured_vision_model, vision_auto_reload_enabled

            if auto_reload and vision_auto_reload_enabled():
                reloaded = await reload_configured_vision_model(client)
                if reloaded:
                    retry = await _describe_attempt(
                        client,
                        base=base,
                        model=model,
                        headers=headers,
                        system_prompt=system_prompt,
                        user_text=user_text,
                        image_b64=image_b64,
                        max_tokens=max_tokens,
                        api_order=order,
                    )
                    if retry.caption:
                        return VisionDescribeOutcome(
                            caption=retry.caption,
                            saw_corrupt=True,
                            reloaded=True,
                            finish_reason=retry.finish_reason,
                            api_route=retry.api_route,
                        )

    return VisionDescribeOutcome(caption=None, saw_corrupt=saw_corrupt, reloaded=reloaded)


async def describe_image_via_lm_studio(image_base64: str) -> str | None:
    """Send JPEG to LM Studio vision; return text-only caption."""
    return (await describe_image_outcome(image_base64)).caption


def format_capture_text(
    result: CaptureResult,
    label: str = "",
    *,
    vision_caption: str | None = None,
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
    elif text_only_tool_results() and vision_describe_enabled():
        lines.append("")
        lines.append("=== VISION_DESCRIBE_FAILED ===")
        lines.append(
            "LM Studio への画像説明リクエストが失敗しました。"
            " 部屋の様子・物体を推測で述べないこと。"
            " ユーザーには file_path の JPEG を開いて確認するよう伝えてください。"
        )
        lines.append("=== END VISION_DESCRIBE_FAILED ===")
    return "\n".join(lines)
