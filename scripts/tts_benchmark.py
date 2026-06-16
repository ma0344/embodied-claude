"""Cold vs warm TTS benchmark for AivisSpeech and Irodori."""

from __future__ import annotations

import json
import statistics
import subprocess
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

PHRASE = (
    "まー、おる？ TTSのベンチテストやで。"
    "ランチやない。ベンチや。お気に入りの声が見つかるとええなぁ。"
)
AIVIS_SPEAKER = 345585728  # るな・ノーマル
COLD_CYCLES = 3
WARM_RUNS = 10
OUT_DIR = Path(__file__).resolve().parent / "tts-samples"

AIVIS_ROOT = Path(r"C:\Users\ma\src\AivisSpeech-Engine\Windows-x64")
IRODORI_ROOT = Path(r"C:\Users\ma\src\Irodori-TTS-Server")


@dataclass
class EngineResult:
    engine: str
    cold_startup_sec: list[float]
    cold_first_synth_sec: list[float]
    warm_synth_sec: list[float]

    @property
    def cold_startup_avg(self) -> float:
        return statistics.mean(self.cold_startup_sec)

    @property
    def cold_first_synth_avg(self) -> float:
        return statistics.mean(self.cold_first_synth_sec)

    @property
    def warm_synth_avg(self) -> float:
        return statistics.mean(self.warm_synth_sec)

    @property
    def warm_synth_stdev(self) -> float:
        return statistics.stdev(self.warm_synth_sec) if len(self.warm_synth_sec) > 1 else 0.0


def stop_port(port: int) -> None:
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | "
                "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force "
                "-ErrorAction SilentlyContinue }"
            ),
        ],
        check=False,
        capture_output=True,
    )
    time.sleep(2)


def wait_http_json(url: str, *, timeout: float, predicate) -> float:
    """Return seconds elapsed until predicate(json) is true."""
    t0 = time.perf_counter()
    deadline = t0 + timeout
    last_error: Exception | None = None
    while time.perf_counter() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                payload = json.loads(resp.read())
            if predicate(payload):
                return time.perf_counter() - t0
        except Exception as exc:  # noqa: PERF203 - polling loop
            last_error = exc
        time.sleep(1)
    raise TimeoutError(f"{url} not ready in {timeout}s (last={last_error})")


def synth_aivis() -> tuple[float, int]:
    t0 = time.perf_counter()
    qurl = "http://127.0.0.1:10101/audio_query?" + urllib.parse.urlencode(
        {"text": PHRASE, "speaker": AIVIS_SPEAKER}
    )
    req = urllib.request.Request(qurl, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        query = json.loads(resp.read())
    req2 = urllib.request.Request(
        f"http://127.0.0.1:10101/synthesis?speaker={AIVIS_SPEAKER}",
        data=json.dumps(query).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req2, timeout=300) as resp:
        wav = resp.read()
    return time.perf_counter() - t0, len(wav)


def synth_irodori() -> tuple[float, int]:
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
    with urllib.request.urlopen(req, timeout=300) as resp:
        wav = resp.read()
    return time.perf_counter() - t0, len(wav)


def start_aivis() -> subprocess.Popen:
    return subprocess.Popen(
        [str(AIVIS_ROOT / "run.exe"), "--use_gpu"],
        cwd=AIVIS_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )


def start_irodori() -> subprocess.Popen:
    return subprocess.Popen(
        [
            "uv",
            "run",
            "--extra",
            "cu128",
            "python",
            "-m",
            "irodori_openai_tts",
            "--host",
            "127.0.0.1",
            "--port",
            "8088",
        ],
        cwd=IRODORI_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )


def bench_aivis() -> EngineResult:
    result = EngineResult("AivisSpeech", [], [], [])
    print("\n=== AivisSpeech ===")
    for cycle in range(1, COLD_CYCLES + 1):
        print(f"  cold cycle {cycle}/{COLD_CYCLES} ...")
        stop_port(10101)
        proc = start_aivis()
        try:
            startup = wait_http_json(
                "http://127.0.0.1:10101/version",
                timeout=180,
                predicate=lambda _: True,
            )
            result.cold_startup_sec.append(startup)
            sec, nbytes = synth_aivis()
            result.cold_first_synth_sec.append(sec)
            print(f"    startup={startup:.2f}s first_synth={sec:.2f}s ({nbytes} bytes)")
        finally:
            stop_port(10101)
            proc.wait(timeout=30)

    print(f"  warm runs x{WARM_RUNS} ...")
    proc = start_aivis()
    try:
        wait_http_json(
            "http://127.0.0.1:10101/version",
            timeout=180,
            predicate=lambda _: True,
        )
        for i in range(WARM_RUNS):
            sec, nbytes = synth_aivis()
            result.warm_synth_sec.append(sec)
            print(f"    warm {i + 1}: {sec:.2f}s ({nbytes} bytes)")
    finally:
        stop_port(10101)
        proc.wait(timeout=30)

    return result


def bench_irodori() -> EngineResult:
    result = EngineResult("Irodori", [], [], [])
    print("\n=== Irodori ===")
    for cycle in range(1, COLD_CYCLES + 1):
        print(f"  cold cycle {cycle}/{COLD_CYCLES} ...")
        stop_port(8088)
        proc = start_irodori()
        try:
            startup = wait_http_json(
                "http://127.0.0.1:8088/health",
                timeout=600,
                predicate=lambda p: p.get("runtime", {}).get("loaded") is True,
            )
            result.cold_startup_sec.append(startup)
            sec, nbytes = synth_irodori()
            result.cold_first_synth_sec.append(sec)
            print(f"    startup={startup:.2f}s first_synth={sec:.2f}s ({nbytes} bytes)")
        finally:
            stop_port(8088)
            proc.wait(timeout=60)

    print(f"  warm runs x{WARM_RUNS} ...")
    proc = start_irodori()
    try:
        wait_http_json(
            "http://127.0.0.1:8088/health",
            timeout=600,
            predicate=lambda p: p.get("runtime", {}).get("loaded") is True,
        )
        for i in range(WARM_RUNS):
            sec, nbytes = synth_irodori()
            result.warm_synth_sec.append(sec)
            print(f"    warm {i + 1}: {sec:.2f}s ({nbytes} bytes)")
            if i == 0:
                OUT_DIR.mkdir(exist_ok=True)
                # keep one warm sample for listening
                body = json.dumps(
                    {
                        "model": "irodori-tts",
                        "input": PHRASE,
                        "voice": "none",
                        "response_format": "wav",
                        "irodori": {"num_steps": 24},
                    }
                ).encode()
                # already synthesized; skip duplicate write
    finally:
        stop_port(8088)
        proc.wait(timeout=60)

    return result


def print_summary(results: list[EngineResult]) -> None:
    print("\n" + "=" * 60)
    print(f"phrase ({len(PHRASE)} chars): {PHRASE}")
    print(f"cold cycles={COLD_CYCLES}, warm runs={WARM_RUNS}")
    print("=" * 60)
    for r in results:
        print(f"\n{r.engine}")
        print(f"  cold startup avg:      {r.cold_startup_avg:.2f}s  {r.cold_startup_sec}")
        print(f"  cold 1st synth avg:    {r.cold_first_synth_avg:.2f}s  {r.cold_first_synth_sec}")
        print(
            f"  warm synth avg:        {r.warm_synth_avg:.2f}s "
            f"(stdev {r.warm_synth_stdev:.2f})"
        )
        print(f"  warm synth all:        {[round(x, 2) for x in r.warm_synth_sec]}")


def main() -> None:
    print("TTS benchmark: cold restart + warm resident")
    results = [bench_aivis(), bench_irodori()]
    print_summary(results)

    report = {
        "phrase": PHRASE,
        "cold_cycles": COLD_CYCLES,
        "warm_runs": WARM_RUNS,
        "results": [
            {
                **asdict(r),
                "cold_startup_avg": r.cold_startup_avg,
                "cold_first_synth_avg": r.cold_first_synth_avg,
                "warm_synth_avg": r.warm_synth_avg,
                "warm_synth_stdev": r.warm_synth_stdev,
            }
            for r in results
        ],
    }
    OUT_DIR.mkdir(exist_ok=True)
    report_path = OUT_DIR / "benchmark-cold-warm.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nreport: {report_path}")

    # restart both for user's normal use
    print("\nrestarting servers for normal use ...")
    start_aivis()
    wait_http_json("http://127.0.0.1:10101/version", timeout=180, predicate=lambda _: True)
    start_irodori()
    wait_http_json(
        "http://127.0.0.1:8088/health",
        timeout=600,
        predicate=lambda p: p.get("runtime", {}).get("loaded") is True,
    )
    print("Aivis :10101 and Irodori :8088 are up again.")


if __name__ == "__main__":
    main()
