"""Backward-compatible re-exports — canonical module is social_core.date_resolution."""

from social_core.date_resolution import (  # noqa: F401
    DEFAULT_TIMEZONE,
    TemporalAnchorResult,
    anchor_relative_dates_in_text,
    anchor_temporal_in_text,
    as_of_date,
    calendar_anchor_line,
    detect_ambiguous_temporal_phrases,
    format_jp_date,
    is_resolved_date_stale,
    is_stale,
    resolve_relative_date,
    resolve_upcoming_weekday,
    stale_from_detail_json,
)

__all__ = [
    "DEFAULT_TIMEZONE",
    "TemporalAnchorResult",
    "anchor_relative_dates_in_text",
    "anchor_temporal_in_text",
    "as_of_date",
    "calendar_anchor_line",
    "detect_ambiguous_temporal_phrases",
    "format_jp_date",
    "is_resolved_date_stale",
    "is_stale",
    "resolve_relative_date",
    "resolve_upcoming_weekday",
    "stale_from_detail_json",
]
