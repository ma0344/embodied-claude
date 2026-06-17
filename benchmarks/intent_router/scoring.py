"""Fixture loading and label comparison for intent_router benchmarks."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class FixtureResult:
    fixture_id: str
    description: str
    user_text: str
    category: str
    expected: list[str]
    rules: list[str]
    llm: list[str] | None = None
    llm_confidence: float | None = None
    llm_raw: str | None = None

    def rules_match(self) -> bool:
        return self.rules == self.expected

    def llm_match(self) -> bool:
        return self.llm is not None and self.llm == self.expected


@dataclass(slots=True)
class SuiteReport:
    results: list[FixtureResult] = field(default_factory=list)

    def explicit(self) -> list[FixtureResult]:
        return [r for r in self.results if r.category == "explicit"]

    def ambiguous(self) -> list[FixtureResult]:
        return [r for r in self.results if r.category == "ambiguous"]

    def rules_explicit_rate(self) -> float:
        items = self.explicit()
        if not items:
            return 1.0
        return sum(1 for r in items if r.rules_match()) / len(items)

    def llm_explicit_rate(self) -> float | None:
        items = [r for r in self.explicit() if r.llm is not None]
        if not items:
            return None
        return sum(1 for r in items if r.llm_match()) / len(items)

    def llm_ambiguous_rate(self) -> float | None:
        items = [r for r in self.ambiguous() if r.llm is not None]
        if not items:
            return None
        return sum(1 for r in items if r.llm_match()) / len(items)


def load_fixtures(fixture_dir: Path) -> list[dict]:
    fixtures: list[dict] = []
    for path in sorted(fixture_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("id", path.stem)
        fixtures.append(data)
    if not fixtures:
        raise FileNotFoundError(f"No fixtures in {fixture_dir}")
    return fixtures


RULES_EXPLICIT_FLOOR = 1.0
