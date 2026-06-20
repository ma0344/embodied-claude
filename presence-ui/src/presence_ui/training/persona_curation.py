"""Persist human rejections and build curated persona LoRA JSONL."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from presence_ui.training.persona_export import (
    PersonaTrainingExample,
    _normalize_pair_text,
    load_persona_jsonl,
)


def training_dir() -> Path:
    return Path.home() / ".claude" / "memories" / "training"


def persona_curated_jsonl_path() -> Path:
    raw = os.getenv("PERSONA_TRAINING_JSONL", "").strip()
    if raw:
        return Path(raw).expanduser()
    return training_dir() / "koyori-persona.jsonl"


def persona_candidates_jsonl_path() -> Path:
    raw = os.getenv("PERSONA_TRAINING_CANDIDATES_JSONL", "").strip()
    if raw:
        return Path(raw).expanduser()
    return training_dir() / "koyori-persona-candidates.jsonl"


def persona_rejected_json_path() -> Path:
    raw = os.getenv("PERSONA_TRAINING_REJECTED_JSON", "").strip()
    if raw:
        return Path(raw).expanduser()
    return training_dir() / "koyori-persona-rejected.json"


def pair_fingerprint(user: str, assistant: str) -> str:
    payload = f"{_normalize_pair_text(user)}\n{_normalize_pair_text(assistant)}"
    return sha256(payload.encode("utf-8")).hexdigest()[:16]


def resolve_candidates_jsonl_path() -> Path:
    """Candidates file, falling back to legacy curated JSONL before first split export."""
    path = persona_candidates_jsonl_path()
    if path.is_file():
        return path
    legacy = persona_curated_jsonl_path()
    if legacy.is_file():
        return legacy
    return path


@dataclass(frozen=True, slots=True)
class PersonaCurationStats:
    candidates: int
    curated: int
    rejected: int


def _preview(text: str, *, limit: int = 80) -> str:
    body = (text or "").strip().replace("\n", " ")
    if len(body) <= limit:
        return body
    return body[: limit - 1] + "…"


def load_rejected_fingerprints() -> set[str]:
    path = persona_rejected_json_path()
    if not path.is_file():
        return set()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    items = raw.get("rejected")
    if not isinstance(items, list):
        return set()
    out: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            fp = str(item.get("fingerprint") or "").strip()
            if fp:
                out.add(fp)
    return out


def load_rejected_records() -> list[dict[str, str]]:
    path = persona_rejected_json_path()
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = raw.get("rejected")
    if not isinstance(items, list):
        return []
    out: list[dict[str, str]] = []
    for item in items:
        if isinstance(item, dict):
            fp = str(item.get("fingerprint") or "").strip()
            if fp:
                out.append(
                    {
                        "fingerprint": fp,
                        "user_preview": str(item.get("user_preview") or ""),
                        "assistant_preview": str(item.get("assistant_preview") or ""),
                        "rejected_at": str(item.get("rejected_at") or ""),
                    }
                )
    return out


def _save_rejected_records(records: list[dict[str, str]]) -> None:
    path = persona_rejected_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"rejected": records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def reject_training_pairs(pairs: list[tuple[str, str]]) -> tuple[int, PersonaCurationStats]:
    """Add pairs to the rejected manifest and rebuild curated JSONL."""
    existing = {row["fingerprint"]: row for row in load_rejected_records()}
    added = 0
    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    for user, assistant in pairs:
        user = (user or "").strip()
        assistant = (assistant or "").strip()
        if not user or not assistant:
            continue
        fp = pair_fingerprint(user, assistant)
        if fp in existing:
            continue
        existing[fp] = {
            "fingerprint": fp,
            "user_preview": _preview(user),
            "assistant_preview": _preview(assistant),
            "rejected_at": now,
        }
        added += 1
    _save_rejected_records(sorted(existing.values(), key=lambda row: row["rejected_at"]))
    stats = apply_persona_curation()
    return added, stats


def curation_stats_from_examples(
    examples: list[PersonaTrainingExample],
    *,
    rejected: set[str] | None = None,
) -> PersonaCurationStats:
    rejected = rejected if rejected is not None else load_rejected_fingerprints()
    curated = sum(
        1 for ex in examples if pair_fingerprint(ex.user, ex.assistant) not in rejected
    )
    return PersonaCurationStats(
        candidates=len(examples),
        curated=curated,
        rejected=len(rejected),
    )


def apply_persona_curation(
    *,
    candidates_path: Path | None = None,
    curated_path: Path | None = None,
) -> PersonaCurationStats:
    """Write curated LoRA JSONL = candidates minus rejected fingerprints."""
    src = candidates_path or resolve_candidates_jsonl_path()
    dst = curated_path or persona_curated_jsonl_path()
    rejected = load_rejected_fingerprints()

    if not src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text("", encoding="utf-8")
        return PersonaCurationStats(candidates=0, curated=0, rejected=len(rejected))

    examples = load_persona_jsonl(src)
    stats = curation_stats_from_examples(examples, rejected=rejected)
    kept: list[PersonaTrainingExample] = [
        ex
        for ex in examples
        if pair_fingerprint(ex.user, ex.assistant) not in rejected
    ]

    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8") as handle:
        for ex in kept:
            record = {
                "messages": [
                    {"role": "system", "content": ex.system},
                    {"role": "user", "content": ex.user},
                    {"role": "assistant", "content": ex.assistant},
                ]
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    return PersonaCurationStats(
        candidates=stats.candidates,
        curated=len(kept),
        rejected=stats.rejected,
    )
