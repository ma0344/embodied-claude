"""Browser/API helpers for reviewing persona LoRA training JSONL."""

from __future__ import annotations

from pydantic import BaseModel, Field

from presence_ui.training.persona_curation import (
    curation_stats_from_examples,
    load_rejected_fingerprints,
    pair_fingerprint,
    persona_candidates_jsonl_path,
    persona_curated_jsonl_path,
    persona_rejected_json_path,
    reject_training_pairs,
    resolve_candidates_jsonl_path,
)
from presence_ui.training.persona_export import load_persona_jsonl


class PersonaTrainingPair(BaseModel):
    index: int
    line_no: int
    fingerprint: str
    user: str
    assistant: str
    rejected: bool = False


class PersonaTrainingReviewResponse(BaseModel):
    candidates_path: str
    curated_path: str
    rejected_path: str
    exists: bool
    candidates_total: int
    curated_total: int
    rejected_total: int
    offset: int
    limit: int
    pairs: list[PersonaTrainingPair] = Field(default_factory=list)
    system_preview: str = ""
    system_chars: int = 0
    preview_command: str = (
        "cd presence-ui && uv run python ..\\scripts\\preview-persona-lora-jsonl.py"
    )
    export_command: str = (
        "cd presence-ui && uv run python ..\\scripts\\export-persona-lora-jsonl.py"
    )


class PersonaRejectPairInput(BaseModel):
    user: str
    assistant: str


class PersonaRejectRequest(BaseModel):
    pairs: list[PersonaRejectPairInput] = Field(default_factory=list)


class PersonaRejectResponse(BaseModel):
    added: int
    candidates_total: int
    curated_total: int
    rejected_total: int


def fetch_persona_training_review(
    *,
    offset: int = 0,
    limit: int = 50,
    system_preview_chars: int = 400,
) -> PersonaTrainingReviewResponse:
    candidates_path = resolve_candidates_jsonl_path()
    curated_path = persona_curated_jsonl_path()
    rejected_path = persona_rejected_json_path()
    offset = max(0, offset)
    limit = max(1, min(limit, 200))

    if not candidates_path.is_file():
        return PersonaTrainingReviewResponse(
            candidates_path=str(persona_candidates_jsonl_path()),
            curated_path=str(curated_path),
            rejected_path=str(rejected_path),
            exists=False,
            candidates_total=0,
            curated_total=0,
            rejected_total=0,
            offset=offset,
            limit=limit,
        )

    examples = load_persona_jsonl(candidates_path)
    rejected_set = load_rejected_fingerprints()
    stats = curation_stats_from_examples(examples, rejected=rejected_set)
    slice_ = examples[offset : offset + limit]
    system = examples[0].system if examples else ""
    preview = system[:system_preview_chars]
    if len(system) > system_preview_chars:
        preview += "…"

    pairs = [
        PersonaTrainingPair(
            index=offset + idx + 1,
            line_no=example.line_no,
            fingerprint=pair_fingerprint(example.user, example.assistant),
            user=example.user,
            assistant=example.assistant,
            rejected=pair_fingerprint(example.user, example.assistant) in rejected_set,
        )
        for idx, example in enumerate(slice_)
    ]

    return PersonaTrainingReviewResponse(
        candidates_path=str(candidates_path),
        curated_path=str(curated_path),
        rejected_path=str(rejected_path),
        exists=True,
        candidates_total=stats.candidates,
        curated_total=stats.curated,
        rejected_total=stats.rejected,
        offset=offset,
        limit=limit,
        system_preview=preview,
        system_chars=len(system),
        pairs=pairs,
    )


def reject_persona_training_pairs(body: PersonaRejectRequest) -> PersonaRejectResponse:
    pairs = [(item.user, item.assistant) for item in body.pairs]
    added, stats = reject_training_pairs(pairs)
    return PersonaRejectResponse(
        added=added,
        candidates_total=stats.candidates,
        curated_total=stats.curated,
        rejected_total=stats.rejected,
    )
