"""Chat image attachment — validate, resize, build LM Studio multimodal data URLs."""

from __future__ import annotations

import base64
import binascii
import io
import logging
import re

from PIL import Image

logger = logging.getLogger(__name__)

CHAT_IMAGE_MARKER = "[image attached]"
CAMERA_SEE_MARKER = "[camera see]"
USER_IMAGE_ATTACHED_BLOCK = (
    "[user_image_attached]\n"
    "まーがチャットに画像を添付した。このターンの image ブロックを見て答える。"
    "部屋カメラの vision_prefetch とは別。"
)
CAMERA_SEE_VIA_SURFACE_BLOCK = (
    "[camera_see_via_surface]\n"
    "Tapo 部屋カメラの直近キャプチャ。このターンの image ブロックを見て答える。"
    "Do NOT call mcp__wifi-cam__see or look_around."
)
_VISION_PREFETCH_TAIL = re.compile(r"\n\[vision_prefetch\][\s\S]*$", re.I)
_GATEWAY_VISION_DIRECTIVE = re.compile(
    r"\n\[Gateway directive — not for the user\][\s\S]*$",
    re.I,
)
_DATA_URL_RE = re.compile(r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$", re.DOTALL)
_ALLOWED_MIMES = frozenset({"image/jpeg", "image/png", "image/webp"})
_MAX_DECODED_BYTES = 4 * 1024 * 1024


def strip_image_base64(raw: str | None) -> str:
    """Accept raw base64 or data URL; return raw base64 only."""
    text = (raw or "").strip()
    if not text:
        return ""
    match = _DATA_URL_RE.match(text)
    if match:
        return match.group(2).strip()
    return text


def _resize_to_jpeg_base64(raw: bytes, *, max_side: int) -> str:
    with Image.open(io.BytesIO(raw)) as img_file:
        img: Image.Image = img_file
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")


def prepare_chat_image_data_url(
    *,
    image_base64: str | None,
    image_mime: str | None = None,
    max_side: int = 768,
) -> str | None:
    """Resize to JPEG and return a data URL for OpenAI-style image_url blocks."""
    raw = strip_image_base64(image_base64)
    if not raw:
        return None
    mime = (image_mime or "image/jpeg").strip().lower()
    if mime not in _ALLOWED_MIMES:
        raise ValueError(f"unsupported image mime: {mime}")
    try:
        decoded = base64.standard_b64decode(raw)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("invalid base64 image") from exc
    if len(decoded) > _MAX_DECODED_BYTES:
        raise ValueError("image too large (max 4MB)")
    if not decoded:
        raise ValueError("empty image")
    resized = _resize_to_jpeg_base64(decoded, max_side=max_side)
    return f"data:image/jpeg;base64,{resized}"


def user_log_text_with_image(
    *,
    raw_user: str,
    image_attached: bool,
    camera_see: bool = False,
) -> str:
    """Session JSONL text — never store base64."""
    body = (raw_user or "").strip()
    if camera_see:
        marker = CAMERA_SEE_MARKER
    elif image_attached:
        marker = CHAT_IMAGE_MARKER
    else:
        return body
    if body:
        return f"{body}\n{marker}"
    return marker


def prepare_enriched_for_user_image(enriched: str) -> str:
    """Drop camera vision_prefetch blocks; mark that the user attached a chat image."""
    text = _strip_vision_prefetch_blocks((enriched or "").strip())
    if USER_IMAGE_ATTACHED_BLOCK in text:
        return text
    return f"{text}\n\n{USER_IMAGE_ATTACHED_BLOCK}".strip()


def _strip_vision_prefetch_blocks(text: str) -> str:
    text = _VISION_PREFETCH_TAIL.sub("", text)
    return _GATEWAY_VISION_DIRECTIVE.sub("", text).strip()


def prepare_enriched_for_camera_see(enriched: str, *, see_mode: str = "current") -> str:
    """Drop e4b vision_prefetch; mark Tapo capture passed as multimodal image."""
    text = _strip_vision_prefetch_blocks((enriched or "").strip())
    block = f"{CAMERA_SEE_VIA_SURFACE_BLOCK}\nmode={see_mode}"
    if block in text:
        return text
    return f"{text}\n\n{block}".strip()


def split_gateway_and_utterance(*, enriched: str, raw_user: str) -> tuple[str, str]:
    """Separate gateway injection from まー's visible utterance."""
    body = (enriched or "").strip()
    utterance = (raw_user or "").strip() or "（画像を添付した）"
    if body and utterance and body.endswith(utterance):
        gateway = body[: -len(utterance)].rstrip()
        return gateway, utterance
    return body, utterance


def image_b64_from_data_url(data_url: str) -> str:
    raw = strip_image_base64(data_url)
    if not raw:
        raise ValueError("empty image data url")
    return raw


def log_prepared_chat_image(data_url: str) -> None:
    try:
        decoded_len = len(base64.standard_b64decode(image_b64_from_data_url(data_url)))
    except (binascii.Error, ValueError):
        decoded_len = -1
    logger.info("chat image prepared for LM Studio (jpeg_bytes=%s)", decoded_len)
