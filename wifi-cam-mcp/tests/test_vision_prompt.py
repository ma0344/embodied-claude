"""Vision prompt layout (system vs user)."""

import pytest

from wifi_cam_mcp.vision import vision_prompt_parts, vision_use_system_prompt


def test_vision_prompt_parts_default_system(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WIFI_CAM_VISION_PROMPT", raising=False)
    monkeypatch.delenv("WIFI_CAM_VISION_USE_SYSTEM", raising=False)
    system, user = vision_prompt_parts()
    assert vision_use_system_prompt()
    assert system is not None
    assert "見えないことは書かない" in system
    assert user == "この写真を説明してください。"


def test_vision_prompt_parts_legacy_user_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WIFI_CAM_VISION_USE_SYSTEM", "0")
    monkeypatch.setenv("WIFI_CAM_VISION_PROMPT", "カスタム指示")
    system, user = vision_prompt_parts()
    assert system is None
    assert user == "カスタム指示"


def test_parse_openai_chat_finish_reason() -> None:
    from wifi_cam_mcp.vision import _parse_openai_chat_content

    text, reason = _parse_openai_chat_content(
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": "窓の外は緑です。"},
                }
            ]
        }
    )
    assert text == "窓の外は緑です。"
    assert reason == "stop"
