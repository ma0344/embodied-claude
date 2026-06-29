#!/usr/bin/env python3
"""OL7 日本語検定型 classifier — manual POC against LM Studio (e4b).

Usage:
  cd presence-ui
  uv run python scripts/ol7_classifier_poc.py
  uv run python scripts/ol7_classifier_poc.py --case poc_c
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass

from presence_ui.gateway.llm_intent import lm_studio_available
from presence_ui.gateway.ol7_return_signal import (
    OpenLoopCandidate,
    classify_return_signal,
)


@dataclass(frozen=True, slots=True)
class PocCase:
    name: str
    open_loops: tuple[OpenLoopCandidate, ...]
    utterance: str
    expect_ids: frozenset[str] | None  # None = informational only
    note: str = ""


POC_A = PocCase(
    name="poc_a_walk",
    open_loops=(
        OpenLoopCandidate(
            loop_id="loop_walk",
            topic="散歩に行く",
            departure_utterance="お昼ご飯を食べたあと散歩に行く",
        ),
    ),
    utterance="ただいま",
    expect_ids=frozenset({"loop_walk"}),
    note="1件 open · 合図",
)

POC_B = PocCase(
    name="poc_b_crab",
    open_loops=(
        OpenLoopCandidate(
            loop_id="loop_crab",
            topic="かにをゆでる",
            departure_utterance="かにをゆでる",
        ),
    ),
    utterance="ゆでた",
    expect_ids=frozenset({"loop_crab"}),
    note="1件 open · 短い完了語",
)

POC_C_LOOPS = (
    OpenLoopCandidate("loop_nap", "お昼寝する", "お昼寝する"),
    OpenLoopCandidate("loop_docs", "書類を作る", "書類を作る"),
    OpenLoopCandidate("loop_mikan", "みかんを食べる", "みかんを食べる"),
)

POC_C_CASES = (
    PocCase("poc_c_greeting", POC_C_LOOPS, "おはよう", frozenset(), "挨拶 → no close"),
    PocCase("poc_c_nap_done", POC_C_LOOPS, "昼寝終わった", frozenset({"loop_nap"}), "明示完了"),
    PocCase(
        "poc_c_gochisousama",
        POC_C_LOOPS,
        "ごちそうさま",
        frozenset(),
        "曖昧合図 → no close（みかんでも食事でも弱い）",
    ),
    PocCase("poc_c_docs_done", POC_C_LOOPS, "書類できた", frozenset({"loop_docs"}), "明示完了"),
)

CASES: dict[str, list[PocCase]] = {
    "all": [POC_A, POC_B, *POC_C_CASES],
    "poc_a": [POC_A],
    "poc_b": [POC_B],
    "poc_c": list(POC_C_CASES),
}


def _result_dict(case: PocCase, parsed) -> dict:
    if parsed is None:
        return {
            "case": case.name,
            "utterance": case.utterance,
            "error": "classifier_failed",
            "note": case.note,
        }
    return {
        "case": case.name,
        "utterance": case.utterance,
        "note": case.note,
        "signal": parsed.signal,
        "close_loop_ids": list(parsed.close_loop_ids),
        "choice_index": parsed.choice_index,
        "confidence": parsed.confidence,
        "completion_summary": parsed.completion_summary,
        "reason": parsed.reason,
        "expect_ids": sorted(case.expect_ids) if case.expect_ids is not None else None,
        "match": (
            frozenset(parsed.close_loop_ids) == case.expect_ids
            if case.expect_ids is not None
            else None
        ),
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass

    parser = argparse.ArgumentParser(description="OL7 classifier POC")
    parser.add_argument(
        "--case",
        choices=[*CASES.keys()],
        default="all",
        help="which scenario set to run",
    )
    parser.add_argument("--json", action="store_true", help="print JSON lines only")
    args = parser.parse_args()

    if not lm_studio_available():
        print(
            "LM Studio unavailable — start server and set PRESENCE_CLASSIFIER_MODEL=e4b",
            file=sys.stderr,
        )
        return 2

    cases = CASES[args.case]
    results: list[dict] = []
    passed = 0
    failed = 0
    skipped = 0

    for case in cases:
        parsed = classify_return_signal(utterance=case.utterance, open_loops=list(case.open_loops))
        row = _result_dict(case, parsed)
        results.append(row)

        if case.expect_ids is None:
            skipped += 1
        elif row.get("match"):
            passed += 1
        else:
            failed += 1

        if not args.json:
            status = "?"
            if case.expect_ids is not None:
                status = "PASS" if row.get("match") else "FAIL"
            print(f"\n=== {case.name} [{status}] ===")
            print(f"note: {case.note}")
            print(f"utterance: {case.utterance}")
            if parsed:
                print(
                    f"→ signal={parsed.signal} ids={list(parsed.close_loop_ids)} "
                    f"conf={parsed.confidence:.2f} reason={parsed.reason!r}"
                )
                if parsed.completion_summary:
                    print(f"  summary: {parsed.completion_summary}")
            else:
                print("→ (classifier failed)")
            if case.expect_ids is not None:
                print(f"expect: {sorted(case.expect_ids)}")

    if args.json:
        for row in results:
            print(json.dumps(row, ensure_ascii=False))
    else:
        print(f"\n--- summary: {passed} pass, {failed} fail, {skipped} info-only ---")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
