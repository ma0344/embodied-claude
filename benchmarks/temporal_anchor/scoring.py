"""Load temporal anchor benchmark fixtures."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Fixture:
    id: str
    description: str
    text: str
    anchor_ts: str
    expected_dates: list[str]
    expected_any_of: bool = False
    rule_should_anchor: bool = False


@dataclass(slots=True)
class FixtureResult:
    fixture: Fixture
    rule_anchored: str | None
    rule_dates: list[str]
    rule_match: bool
    llm_dates: list[str] | None = None
    llm_confidence_min: float | None = None
    llm_anchored: str | None = None
    llm_raw: str | None = None
    llm_error: str | None = None

    def llm_match(self) -> bool | None:
        if self.llm_dates is None:
            return None
        return _dates_match(
            self.llm_dates,
            self.fixture.expected_dates,
            any_of=self.fixture.expected_any_of,
        )


def _dates_match(found: list[str], expected: list[str], *, any_of: bool) -> bool:
    found_set = set(found)
    if any_of:
        return bool(found_set & set(expected))
    return set(expected).issubset(found_set)


def load_fixtures(directory: Path) -> list[Fixture]:
    items: list[Fixture] = []
    for path in sorted(directory.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        items.append(
            Fixture(
                id=str(raw["id"]),
                description=str(raw.get("description", "")),
                text=str(raw["text"]),
                anchor_ts=str(raw["anchor_ts"]),
                expected_dates=[str(d) for d in raw["expected_dates"]],
                expected_any_of=bool(raw.get("expected_any_of", False)),
                rule_should_anchor=bool(raw.get("rule_should_anchor", False)),
            )
        )
    return items


def rule_match(rule_dates: list[str], fixture: Fixture) -> bool:
    if not fixture.rule_should_anchor:
        return True
    return _dates_match(rule_dates, fixture.expected_dates, any_of=fixture.expected_any_of)
