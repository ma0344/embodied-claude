"""Chat image attachment helpers."""

from __future__ import annotations

import base64

import pytest

from presence_ui.services.chat_image import (
    CHAT_IMAGE_MARKER,
    prepare_chat_image_data_url,
    prepare_enriched_for_user_image,
    strip_image_base64,
    user_log_text_with_image,
)


def _tiny_png_b64() -> str:
    # 1x1 PNG
    raw = base64.standard_b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    return base64.standard_b64encode(raw).decode("utf-8")


def test_strip_image_base64_accepts_data_url() -> None:
    raw = _tiny_png_b64()
    assert strip_image_base64(f"data:image/png;base64,{raw}") == raw


def test_prepare_chat_image_data_url() -> None:
    url = prepare_chat_image_data_url(image_base64=_tiny_png_b64(), image_mime="image/png")
    assert url is not None
    assert url.startswith("data:image/jpeg;base64,")


def test_prepare_chat_image_rejects_bad_mime() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        prepare_chat_image_data_url(image_base64=_tiny_png_b64(), image_mime="image/gif")


def test_user_log_text_with_image() -> None:
    assert user_log_text_with_image(raw_user="これ", image_attached=True) == (
        f"これ\n{CHAT_IMAGE_MARKER}"
    )
    assert user_log_text_with_image(raw_user="", image_attached=True) == CHAT_IMAGE_MARKER


def test_prepare_enriched_for_user_image_strips_camera_prefetch() -> None:
    enriched = "[gateway_turn_context]\n\n写真見える？\n\n[vision_prefetch]\nmode=current\n=== VISION_CAPTION ===\n部屋"
    cleaned = prepare_enriched_for_user_image(enriched)
    assert "[vision_prefetch]" not in cleaned
    assert "[user_image_attached]" in cleaned
