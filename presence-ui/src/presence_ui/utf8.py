"""UTF-8 JSON responses for Presence UI."""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse
from pydantic import BaseModel


def utf8_json(data: BaseModel | dict[str, Any]) -> JSONResponse:
    content = data.model_dump(mode="json") if isinstance(data, BaseModel) else data
    return JSONResponse(content=content, media_type="application/json; charset=utf-8")
