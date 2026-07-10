"""Load Koyori Irodori inference profile from TOML."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@dataclass(frozen=True)
class IrodoriProfile:
    """Synthesis recipe for POST /v1/audio/speech irodori block."""

    voice: str = "none"
    seed: int | None = None
    num_steps: int = 24
    cfg_scale_text: float | None = None
    cfg_scale_caption: float | None = None
    cfg_scale_speaker: float | None = None
    caption: str | None = None

    @property
    def cache_label(self) -> str:
        cap = (self.caption or "").strip()
        cap_key = cap[:48].replace("\n", " ") if cap else ""
        return ":".join(
            [
                self.voice,
                str(self.num_steps),
                str(self.seed),
                str(self.cfg_scale_text),
                str(self.cfg_scale_caption),
                str(self.cfg_scale_speaker),
                cap_key,
            ]
        )


def default_profile_path() -> Path:
    explicit = os.getenv("IRODORI_PROFILE_PATH", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return Path.home() / ".config" / "embodied-claude" / "irodori-profile.toml"


def _optional_int(raw: object, *, field: str) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"profile {field} must be an integer, got {raw!r}") from exc


def _optional_float(raw: object, *, field: str) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"profile {field} must be a number, got {raw!r}") from exc


def _caption_default(data: dict) -> str | None:
    caption = data.get("caption")
    if not isinstance(caption, dict):
        return None
    raw = caption.get("default")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def load_irodori_profile(path: Path | None = None) -> IrodoriProfile | None:
    """Load profile TOML. Returns None if file is missing."""
    profile_path = path or default_profile_path()
    if not profile_path.is_file():
        return None
    with profile_path.open("rb") as handle:
        data = tomllib.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"profile root must be a table: {profile_path}")
    section = data.get("profile")
    if not isinstance(section, dict):
        raise ValueError(f"profile table [profile] required: {profile_path}")

    voice_raw = section.get("voice", "none")
    voice = str(voice_raw).strip() if str(voice_raw).strip() else "none"

    num_steps = _optional_int(section.get("num_steps", 24), field="profile.num_steps")
    if num_steps is None or num_steps < 1:
        raise ValueError(f"profile.num_steps must be >= 1, got {num_steps!r}")

    cfg = section.get("cfg")
    cfg_table = cfg if isinstance(cfg, dict) else {}

    return IrodoriProfile(
        voice=voice,
        seed=_optional_int(section.get("seed"), field="profile.seed"),
        num_steps=num_steps,
        cfg_scale_text=_optional_float(cfg_table.get("text"), field="profile.cfg.text"),
        cfg_scale_caption=_optional_float(
            cfg_table.get("caption"), field="profile.cfg.caption"
        ),
        cfg_scale_speaker=_optional_float(
            cfg_table.get("speaker"), field="profile.cfg.speaker"
        ),
        caption=_caption_default(section),
    )
