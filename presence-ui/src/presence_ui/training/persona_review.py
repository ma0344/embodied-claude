"""Browser/API helpers for reviewing persona LoRA training JSONL."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

from presence_ui.training.persona_export import PersonaTrainingExample, load_persona_jsonl


class PersonaTrainingPair(BaseModel):
    index: int
    line_no: int
    user: str
    assistant: str


class PersonaTrainingReviewResponse(BaseModel):
    path: str
    exists: bool
    total: int
    offset: int
    limit: int
    system_preview: str = ""
    system_chars: int = 0
    pairs: list[PersonaTrainingPair] = Field(default_factory=list)
    preview_command: str = (
        "cd presence-ui && uv run python ..\\scripts\\preview-persona-lora-jsonl.py"
    )
    export_command: str = (
        "cd presence-ui && uv run python ..\\scripts\\export-persona-lora-jsonl.py"
    )


def persona_training_jsonl_path() -> Path:
    raw = os.getenv("PERSONA_TRAINING_JSONL", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".claude" / "memories" / "training" / "koyori-persona.jsonl"


def fetch_persona_training_review(
    *,
    offset: int = 0,
    limit: int = 50,
    system_preview_chars: int = 400,
) -> PersonaTrainingReviewResponse:
    path = persona_training_jsonl_path()
    offset = max(0, offset)
    limit = max(1, min(limit, 200))

    if not path.is_file():
        return PersonaTrainingReviewResponse(
            path=str(path),
            exists=False,
            total=0,
            offset=offset,
            limit=limit,
        )

    examples = load_persona_jsonl(path)
    total = len(examples)
    slice_ = examples[offset : offset + limit]
    system = examples[0].system if examples else ""
    preview = system[:system_preview_chars]
    if len(system) > system_preview_chars:
        preview += "…"

    pairs = [
        PersonaTrainingPair(
            index=offset + idx + 1,
            line_no=example.line_no,
            user=example.user,
            assistant=example.assistant,
        )
        for idx, example in enumerate(slice_)
    ]

    return PersonaTrainingReviewResponse(
        path=str(path),
        exists=True,
        total=total,
        offset=offset,
        limit=limit,
        system_preview=preview,
        system_chars=len(system),
        pairs=pairs,
    )
