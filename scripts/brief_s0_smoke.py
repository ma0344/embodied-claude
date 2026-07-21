#!/usr/bin/env python3
"""Run Brief S0 smoke utterances against LM Studio classifier (e4b).

Usage (from repo root or presence-ui):
  cd presence-ui && uv run python ../scripts/brief_s0_smoke.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ROOT / "docs" / "tracks" / "brief-s0-system-prompt.md"
sys.path.insert(0, str(ROOT / "presence-ui" / "src"))

from presence_ui.gateway.gw_silent import lm_studio_available, run_classifier_turn  # noqa: E402
from presence_ui.gateway.llm_intent import _extract_json_object  # noqa: E402
from presence_ui.gateway.brief_s0_reasoning import brief_s0_reasoning_enabled  # noqa: E402


def _load_system() -> str:
    text = PROMPT_PATH.read_text(encoding="utf-8")
    start = text.find("```\n")
    end = text.find("\n```\n\nUser message")
    if start < 0 or end < 0:
        raise SystemExit(f"cannot find fenced prompt in {PROMPT_PATH}")
    return text[start + 4 : end].strip()


# id, utterance, expected notes (human)
CASES: list[tuple[str, str, str]] = [
    ("G1", "カレー食べた", "report/household"),
    ("G2", "今夜カレーにする", "report/household"),
    ("G7", "今夜カレーにしといて", "request/household"),
    ("G3", "いいね全部のせ", "report"),
    (
        "G4",
        "冷蔵庫に卵と玉ねぎあるんだけど、何かアイデアある？それで晩ごはんお願い",
        "consult+request",
    ),
    ("G5", "おはよう。昨夜眠れず。会議憂鬱", "greeting/report/consult"),
    ("G6", "違う、明日じゃなくて明後日", "correction"),
    ("G8", "あーね", "other"),
    ("G9", "しまった。つまみを買ってくるの忘れてた。", "report×1 household"),
    (
        "G10",
        "豆腐、もやし、きゅうり、冷凍のひき肉、納豆、卵、紅生姜、他にも色々あるけど、なんかいいアイデアある？",
        "consult×1 household",
    ),
    ("G11", "ええ天気やね。外、めちゃくちゃ暑そう。", "report×1 merge"),
    ("G12", "明日の朝ごはん何にしよう？", "consult/household"),
    ("G13", "ちなみに、いま、外の気温はどれくらい？", "consult/life"),
    (
        "G14",
        "今、松本の気温、結構上がっているでしょ？もう外に出る気になれん（笑）\nこれは家にあるもんでなんとかするしかないな",
        "consult+report or 1×report",
    ),
    (
        "G15",
        "そういえば、僕の生活にかかわることって、あんまり話してなかったね。\n"
        "僕は COMMON SENSE MATSUMOTO合同会社 っていう会社で 業務執行役員 をしている。\n"
        "その会社は グループホームコモンセンス松本 っていう名前で事業指定を受けて"
        "「ここっち」っていう名前のグループホームを運営しているんだ。",
        "report×1〜2 life",
    ),
    (
        "G16",
        "あの『ADHDの僕がグループホームを作ったら、モヤモヤに包まれた』なんだけど、\n"
        "第一章の「障害に甘えてしまう」のところが気になってて、うちの現場でも似た空気ある気がするんよ。\n"
        "そのあたり、どう読むのが自然やと思う？この間の第一章の続きとして、そこから一緒に読める？",
        "report+consult+request · no title other",
    ),
]


def _score(case_id: str, spans: list[dict]) -> str:
    asks = [str(s.get("ask") or "") for s in spans]
    hints = [str(s.get("hint") or "none") for s in spans]
    n = len(spans)
    # adjacent same-ask
    adj = any(asks[i] == asks[i + 1] for i in range(n - 1))

    if case_id == "G1":
        return "PASS" if asks == ["report"] and hints[0] == "household" else "FAIL"
    if case_id == "G2":
        return "PASS" if asks == ["report"] else "FAIL"
    if case_id == "G7":
        return "PASS" if asks == ["request"] else "FAIL"
    if case_id == "G3":
        return "PASS" if asks == ["report"] else "FAIL"
    if case_id == "G4":
        return "PASS" if asks == ["consult", "request"] else "FAIL"
    if case_id == "G5":
        return "PASS" if asks == ["greeting", "report", "consult"] else "FAIL"
    if case_id == "G6":
        return "PASS" if asks == ["correction"] else "FAIL"
    if case_id == "G8":
        return "PASS" if asks == ["other"] else "FAIL"
    if case_id == "G9":
        return "PASS" if asks == ["report"] and n == 1 else "FAIL"
    if case_id == "G10":
        return (
            "PASS"
            if asks == ["consult"] and n == 1 and hints[0] == "household"
            else "FAIL"
        )
    if case_id == "G11":
        return "PASS" if asks == ["report"] and n == 1 and not adj else "FAIL"
    if case_id == "G12":
        return "PASS" if asks == ["consult"] else "FAIL"
    if case_id == "G13":
        return "PASS" if asks == ["consult"] else "FAIL"
    if case_id == "G14":
        # Preferred: consult+report; alt: single report. Never adjacent same-ask.
        if adj or n > 2:
            return "FAIL"
        if asks == ["consult", "report"] or asks == ["report"]:
            return "PASS"
        return "FAIL"
    if case_id == "G15":
        # Framing+body as 1–2 reports OK; 3+ sentence splits FAIL.
        if n > 2 or any(a != "report" for a in asks):
            return "FAIL"
        if asks in (["report"], ["report", "report"]):
            return "PASS"
        return "FAIL"
    if case_id == "G16":
        # report + consult + request; title must not be ask=other.
        if "other" in asks:
            return "FAIL"
        if asks == ["report", "consult", "request"]:
            return "PASS"
        # Title folded into consult somehow is still wrong if request/consult missing.
        return "FAIL"
    return "UNKNOWN"


def main() -> int:
    if not lm_studio_available(timeout=2.0):
        print("LM Studio unavailable")
        return 2
    system = _load_system()
    use_reasoning = brief_s0_reasoning_enabled()
    print(f"reasoning={use_reasoning} (PRESENCE_BRIEF_S0_REASONING)")
    results: list[tuple[str, str, list, str]] = []
    for case_id, utterance, expected in CASES:
        raw = run_classifier_turn(
            system=system,
            user=f"Utterance:\n{utterance}",
            max_tokens=1536 if use_reasoning else 512,
            temperature=0.2,
            log_label=f"Brief S0 smoke {case_id}",
            reasoning=use_reasoning,
            timeout=90.0 if use_reasoning else 45.0,
        )
        data = _extract_json_object(raw or "") if raw else None
        spans = list(data.get("spans") or []) if isinstance(data, dict) else []
        if not isinstance(spans, list):
            spans = []
        spans = [s for s in spans if isinstance(s, dict)]
        verdict = _score(case_id, spans) if spans else "FAIL"
        compact = [
            {"ask": s.get("ask"), "hint": s.get("hint"), "text": str(s.get("text") or "")[:40]}
            for s in spans
        ]
        results.append((case_id, verdict, compact, expected))
        print(f"{case_id}\t{verdict}\texpect={expected}\tgot={json.dumps(compact, ensure_ascii=False)}")

    passed = sum(1 for _, v, _, _ in results if v == "PASS")
    print(f"\n{passed}/{len(results)} PASS")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
