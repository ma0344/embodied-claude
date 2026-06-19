"""Run temporal anchor benchmark — rules baseline + optional utility LLM.

Usage::

    cd presence-ui
    $env:PRESENCE_LLM_UTILITY_MODEL = "qwen2.5-3b-instruct"
    uv run python ../benchmarks/temporal_anchor/run_suite.py --llm
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
FIXTURE_DIR = BENCH_DIR / "fixtures"

if str(BENCH_DIR) not in sys.path:
    sys.path.insert(0, str(BENCH_DIR))

from scoring import FixtureResult, load_fixtures, rule_match  # noqa: E402
from temporal_llm import (  # noqa: E402
    classify_temporal_with_llm,
    lm_studio_available,
    utility_model,
)

from social_core.date_resolution import anchor_relative_dates_in_text, resolve_relative_date  # noqa: E402
from social_core.ja_timex_bridge import extract_timex_spans, ja_timex_available  # noqa: E402


def _rule_dates(text: str, anchor_ts: str) -> tuple[str, list[str]]:
    anchored, _ = anchor_relative_dates_in_text(
        text, updated_at=anchor_ts, tz_name="Asia/Tokyo"
    )
    resolved = resolve_relative_date(topic=text, updated_at=anchor_ts, tz_name="Asia/Tokyo")
    dates = [resolved.isoformat()] if resolved else []
    return anchored, dates


def run_suite(*, use_llm: bool = False, use_ja_timex: bool = False, model: str | None = None) -> list[FixtureResult]:
    results: list[FixtureResult] = []
    llm_ok = use_llm and lm_studio_available()
    chosen = model or utility_model()

    for fixture in load_fixtures(FIXTURE_DIR):
        anchored, dates = _rule_dates(fixture.text, fixture.anchor_ts)
        row = FixtureResult(
            fixture=fixture,
            rule_anchored=anchored if anchored != fixture.text else None,
            rule_dates=dates,
            rule_match=rule_match(dates, fixture),
        )
        if llm_ok:
            llm_dates, min_conf, llm_anchored, raw = classify_temporal_with_llm(
                fixture.text,
                anchor_ts=fixture.anchor_ts,
                model=chosen,
            )
            row.llm_dates = llm_dates
            row.llm_confidence_min = min_conf
            row.llm_anchored = llm_anchored
            if row.llm_match() is False and raw and not raw.startswith("HTTP"):
                row.llm_raw = raw[:400]
            elif raw and (raw.startswith("HTTP") or raw in {"empty choices", "empty content"}):
                row.llm_error = raw
        results.append(row)
    return results


def _print_report(
    results: list[FixtureResult], *, use_llm: bool, use_ja_timex: bool, model: str
) -> int:
    llm_hits = 0
    llm_ran = 0
    rule_rule_cases = [r for r in results if r.fixture.rule_should_anchor]
    rule_hits = sum(1 for r in rule_rule_cases if r.rule_match)

    for row in results:
        status = "PASS" if row.rule_match else "SKIP"
        if row.fixture.rule_should_anchor and not row.rule_match:
            status = "FAIL"
        print(f"[rule {status}] {row.fixture.id}: {row.fixture.description}")
        print(f"    text: {row.fixture.text[:80]}")
        print(f"    expected: {row.fixture.expected_dates}")
        if row.rule_dates:
            print(f"    rule dates: {row.rule_dates}")
        if use_ja_timex:
            if ja_timex_available():
                spans = extract_timex_spans(
                    row.fixture.text, anchor_ts=row.fixture.anchor_ts, tz_name="Asia/Tokyo"
                )
                print(f"    ja-timex: {spans}")
            else:
                print("    ja-timex: not installed (use Python 3.12 + pip install ja-timex)")
        if use_llm:
            if row.llm_dates is None and row.llm_error:
                print(f"    llm ERROR: {row.llm_error}")
            elif row.llm_dates is not None:
                llm_ran += 1
                match = row.llm_match()
                if match:
                    llm_hits += 1
                tag = "PASS" if match else "FAIL"
                print(
                    f"    llm {tag}: dates={row.llm_dates} "
                    f"conf_min={row.llm_confidence_min}"
                )
                if row.llm_anchored and row.llm_anchored != row.fixture.text:
                    print(f"    anchored: {row.llm_anchored[:120]}")
                if tag == "FAIL" and row.llm_raw:
                    print(f"    raw: {row.llm_raw[:200]}")

    print("\n== Summary ==")
    print(f"  fixtures: {len(results)}")
    print(f"  rule cases (OL1b/OL1c): {rule_hits}/{len(rule_rule_cases)}")
    if use_llm:
        if lm_studio_available():
            print(f"  model: {model}")
            print(f"  llm match: {llm_hits}/{llm_ran}")
            if llm_ran and llm_hits < llm_ran:
                return 1
        else:
            print("  llm: LM Studio not reachable")
            return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Temporal anchor benchmark (OL2-temporal)")
    parser.add_argument("--llm", action="store_true", help="Call utility LLM via LM Studio")
    parser.add_argument("--ja-timex", action="store_true", help="Print ja-timex spans per fixture")
    parser.add_argument("--model", default=None, help="Override utility model id")
    args = parser.parse_args()
    model = args.model or utility_model()
    results = run_suite(use_llm=args.llm, use_ja_timex=args.ja_timex, model=model)
    return _print_report(results, use_llm=args.llm, use_ja_timex=args.ja_timex, model=model)


if __name__ == "__main__":
    raise SystemExit(main())
