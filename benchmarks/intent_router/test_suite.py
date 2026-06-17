"""pytest entry for IBF-7 intent_router benchmark.

Run from presence-ui venv::

    uv run --directory presence-ui pytest ../benchmarks/intent_router/test_suite.py -v

Optional LLM pass (LM Studio must be up)::

    uv run --directory presence-ui pytest ../benchmarks/intent_router/test_suite.py -v -k llm
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BENCH_DIR = Path(__file__).resolve().parent
if str(BENCH_DIR) not in sys.path:
    sys.path.insert(0, str(BENCH_DIR))

from run_suite import run_suite  # noqa: E402
from scoring import RULES_EXPLICIT_FLOOR  # noqa: E402
from llm_router import lm_studio_available  # noqa: E402


def test_rules_explicit_fixtures_match_golden():
    report = run_suite(use_llm=False)
    rate = report.rules_explicit_rate()
    failures = [
        (r.fixture_id, r.expected, r.rules)
        for r in report.explicit()
        if not r.rules_match()
    ]
    assert rate >= RULES_EXPLICIT_FLOOR, f"rules explicit {rate:.2f}; failures={failures}"


@pytest.mark.skipif(not lm_studio_available(), reason="LM Studio not reachable")
def test_llm_explicit_agreement_report():
    """Informational floor — logs agreement; does not block CI if LLM drifts."""
    report = run_suite(use_llm=True)
    rate = report.llm_explicit_rate()
    assert rate is not None
    # Soft floor for experiment phase — tighten when C12 ships.
    assert rate >= 0.5, f"llm explicit agreement {rate:.0%} below 50%"
