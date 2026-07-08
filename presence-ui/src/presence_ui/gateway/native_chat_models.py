"""Native chat request models (extends claude-code-server with multimodal fields)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NativeChatRequest(BaseModel):
    """Incoming native chat request — surface direct + optional image attachment."""

    prompt: str = ""
    session_id: str | None = None
    system_prompt: str | None = None
    append_system_prompt: str | None = None
    inbound_nudge: str | None = None
    inbound_nudge_id: str | None = None
    image_base64: str | None = Field(
        default=None,
        description="Raw base64 (no data: prefix) for one attached image",
    )
    image_mime: str | None = Field(
        default=None,
        description="image/jpeg | image/png | image/webp",
    )
