"""Browser/API helpers for inner persona LoRA training JSONL (RP-2c)."""

from __future__ import annotations

from presence_ui.training.persona_curation import (
    PersonaCurationStats,
    apply_persona_inner_curation,
    curation_stats_from_examples,
    load_rejected_fingerprints,
    pair_fingerprint,
    persona_inner_candidates_jsonl_path,
    persona_inner_curated_jsonl_path,
    persona_inner_rejected_json_path,
    reject_inner_training_pairs,
    resolve_inner_candidates_jsonl_path,
)
from presence_ui.training.persona_export import PersonaExportStats, load_persona_jsonl
from presence_ui.training.persona_inner_export import export_persona_inner_jsonl
from presence_ui.training.persona_review import (
    PersonaExportResponse,
    PersonaRejectRequest,
    PersonaRejectResponse,
    PersonaTrainingPair,
    PersonaTrainingReviewResponse,
)
from presence_ui.training.cheerleader_strip import strip_trailing_cheerleader_closings


def fetch_persona_inner_training_review(
    *,
    offset: int = 0,
    limit: int = 50,
    system_preview_chars: int = 400,
) -> PersonaTrainingReviewResponse:
    candidates_path = resolve_inner_candidates_jsonl_path()
    curated_path = persona_inner_curated_jsonl_path()
    rejected_path = persona_inner_rejected_json_path()
    offset = max(0, offset)
    limit = max(1, min(limit, 200))

    if not candidates_path.is_file():
        return PersonaTrainingReviewResponse(
            candidates_path=str(persona_inner_candidates_jsonl_path()),
            curated_path=str(curated_path),
            rejected_path=str(rejected_path),
            exists=False,
            candidates_total=0,
            curated_total=0,
            rejected_total=0,
            offset=offset,
            limit=limit,
            preview_command=(
                "cd presence-ui && uv run python ..\\scripts\\export-persona-inner-jsonl.py"
            ),
            export_command=(
                "cd presence-ui && uv run python ..\\scripts\\export-persona-inner-jsonl.py"
            ),
        )

    examples = load_persona_jsonl(candidates_path)
    rejected_set = load_rejected_fingerprints(rejected_path)
    stats = curation_stats_from_examples(examples, rejected=rejected_set)
    slice_ = examples[offset:offset + limit]
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
            assistant=strip_trailing_cheerleader_closings(example.assistant),
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
        preview_command=(
            "cd presence-ui && uv run python ..\\scripts\\export-persona-inner-jsonl.py"
        ),
        export_command=(
            "cd presence-ui && uv run python ..\\scripts\\export-persona-inner-jsonl.py"
        ),
        pairs=pairs,
    )


def reject_persona_inner_training_pairs(body: PersonaRejectRequest) -> PersonaRejectResponse:
    pairs = [(item.user, item.assistant) for item in body.pairs]
    added, stats = reject_inner_training_pairs(pairs)
    return PersonaRejectResponse(
        added=added,
        candidates_total=stats.candidates,
        curated_total=stats.curated,
        rejected_total=stats.rejected,
    )


def run_persona_inner_training_export(
    *,
    max_rows: int = 500,
) -> PersonaExportResponse:
    from presence_ui.gateway.ccs_integration import embodied_repo_root

    candidates_path = persona_inner_candidates_jsonl_path()
    curated_path = persona_inner_curated_jsonl_path()
    try:
        stats: PersonaExportStats = export_persona_inner_jsonl(
            repo_root=embodied_repo_root(),
            output_path=candidates_path,
            max_rows=max_rows,
        )
        curation: PersonaCurationStats = apply_persona_inner_curation(
            candidates_path=candidates_path,
            curated_path=curated_path,
        )
    except FileNotFoundError as exc:
        return PersonaExportResponse(
            ok=False,
            candidates_path=str(candidates_path),
            curated_path=str(curated_path),
            error=str(exc),
        )
    except OSError as exc:
        return PersonaExportResponse(
            ok=False,
            candidates_path=str(candidates_path),
            curated_path=str(curated_path),
            error=str(exc),
        )

    return PersonaExportResponse(
        ok=True,
        sessions_scanned=stats.sessions_scanned,
        pairs_written=stats.pairs_written,
        pairs_skipped=stats.pairs_skipped,
        curated_total=curation.curated,
        rejected_total=curation.rejected,
        candidates_path=str(candidates_path),
        curated_path=str(curated_path),
    )
