"""Run IBF-7 intent_router benchmark (rules + optional LM Studio).

Usage::

    uv run --directory presence-ui python ../benchmarks/intent_router/run_suite.py
    uv run --directory presence-ui python ../benchmarks/intent_router/run_suite.py --llm
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
FIXTURE_DIR = BENCH_DIR / "fixtures"

if str(BENCH_DIR) not in sys.path:
    sys.path.insert(0, str(BENCH_DIR))

from llm_router import classify_with_llm, lm_studio_available  # noqa: E402
from rule_router import classify_with_rules  # noqa: E402
from scoring import FixtureResult, SuiteReport, load_fixtures  # noqa: E402


def run_suite(*, use_llm: bool = False) -> SuiteReport:
    report = SuiteReport()
    llm_ok = use_llm and lm_studio_available()
    for fixture in load_fixtures(FIXTURE_DIR):
        text = str(fixture["user_text"])
        expected = sorted(fixture["expected_labels"])
        rules = classify_with_rules(text)
        llm_labels: list[str] | None = None
        llm_conf: float | None = None
        llm_raw: str | None = None
        if llm_ok:
            llm_labels, llm_conf, llm_raw = classify_with_llm(text)
        report.results.append(
            FixtureResult(
                fixture_id=str(fixture["id"]),
                description=str(fixture.get("description", "")),
                user_text=text,
                category=str(fixture.get("category", "explicit")),
                expected=expected,
                rules=rules,
                llm=llm_labels,
                llm_confidence=llm_conf,
                llm_raw=llm_raw if llm_ok else None,
            )
        )
    return report


def _print_report(report: SuiteReport, *, use_llm: bool) -> int:
    import sys

    def safe_print(msg: str) -> None:
        try:
            print(msg)
        except UnicodeEncodeError:
            sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))
    for row in report.results:
        status = "PASS" if row.rules_match() else "FAIL"
        if row.category == "ambiguous":
            status = "AMBIG"
        line = f"[{status}] {row.fixture_id}: {row.description}"
        safe_print(line)
        safe_print(f"    text: {row.user_text}")
        safe_print(f"    expected: {row.expected}")
        safe_print(f"    rules:    {row.rules}")
        if row.llm is not None:
            match = "ok" if row.llm_match() else "DIFF"
            safe_print(f"    llm({match}): {row.llm} conf={row.llm_confidence}")
        elif use_llm:
            safe_print("    llm: (skipped)")

    explicit = report.explicit()
    amb = report.ambiguous()
    rules_hits = sum(1 for r in explicit if r.rules_match())
    print("\n== Summary ==")
    print(f"  fixtures: {len(report.results)} ({len(explicit)} explicit, {len(amb)} ambiguous)")
    print(f"  rules explicit match: {rules_hits}/{len(explicit)} ({report.rules_explicit_rate():.0%})")
    if use_llm:
        if lm_studio_available():
            llm_exp = report.llm_explicit_rate()
            llm_amb = report.llm_ambiguous_rate()
            if llm_exp is not None:
                print(f"  llm explicit match:   {llm_exp:.0%}")
            if llm_amb is not None:
                print(f"  llm ambiguous match:  {llm_amb:.0%}")
        else:
            print("  llm: LM Studio not reachable (set ANTHROPIC_BASE_URL / token)")

    if report.rules_explicit_rate() < 1.0:
        print("SUITE FAIL: rules missed explicit fixture(s)")
        return 1
    print("SUITE PASS (rules)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="IBF-7 intent router benchmark")
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Also call LM Studio (offline experiment)",
    )
    args = parser.parse_args()
    report = run_suite(use_llm=args.llm)
    return _print_report(report, use_llm=args.llm)


if __name__ == "__main__":
    raise SystemExit(main())
