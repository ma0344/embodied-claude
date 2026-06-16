"""Generate A/B TTS samples: AivisSpeech vs Irodori."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

PHRASE = "まー、おる？ TTSのテストやで。お気に入りの声が見つかるとええなぁ。"
AIVIS_SPEAKER = 345585728  # るな・ノーマル
OUT_DIR = Path(__file__).resolve().parent / "tts-samples"


def aivis(speaker: int, filename: str) -> float:
    t0 = time.perf_counter()
    qurl = "http://127.0.0.1:10101/audio_query?" + urllib.parse.urlencode(
        {"text": PHRASE, "speaker": speaker}
    )
    req = urllib.request.Request(qurl, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        query = json.loads(resp.read())
    req2 = urllib.request.Request(
        f"http://127.0.0.1:10101/synthesis?speaker={speaker}",
        data=json.dumps(query).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req2, timeout=120) as resp:
        wav = resp.read()
    path = OUT_DIR / filename
    path.write_bytes(wav)
    return time.perf_counter() - t0


def irodori(filename: str) -> float:
    t0 = time.perf_counter()
    body = json.dumps(
        {
            "model": "irodori-tts",
            "input": PHRASE,
            "voice": "none",
            "response_format": "wav",
            "irodori": {"num_steps": 24},
        }
    ).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8088/v1/audio/speech",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        wav = resp.read()
    path = OUT_DIR / filename
    path.write_bytes(wav)
    return time.perf_counter() - t0


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    print(f"phrase: {PHRASE}")

    sec = aivis(AIVIS_SPEAKER, "aivis-runa-normal-long.wav")
    print(f"Aivis (るな・ノーマル): {sec:.2f}s")

    try:
        sec3 = irodori("irodori-none-long.wav")
        print(f"Irodori (none): {sec3:.2f}s")
    except Exception as exc:
        print(f"Irodori skipped: {exc}")


if __name__ == "__main__":
    main()
