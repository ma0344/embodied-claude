#!/usr/bin/env python3
"""Localhost helper: system volume overlay hint for kiosk hardware keys (C11f+)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = os.environ.get("KOYORI_AUDIO_HOST", "127.0.0.1")
PORT = int(os.environ.get("KOYORI_AUDIO_PORT", "18791"))
AUDIO_USER = os.environ.get("KOYORI_AUDIO_USER", "ma")
OVERLAY_TTL_SEC = float(os.environ.get("KOYORI_VOLUME_OVERLAY_TTL_SEC", "2.8"))

_state_lock = threading.Lock()
_last_notify = 0.0
_last_percent = 0
_last_muted = False


def _audio_env() -> dict[str, str]:
    env = os.environ.copy()
    uid = subprocess.check_output(["id", "-u", AUDIO_USER], text=True).strip()
    env["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"
    return env


def _run_audio_command(argv: list[str]) -> subprocess.CompletedProcess[str]:
    env = _audio_env()
    if os.getuid() == int(env["XDG_RUNTIME_DIR"].rsplit("/", 1)[-1]):
        return subprocess.run(argv, capture_output=True, text=True, check=False, env=env)
    return subprocess.run(
        [
            "sudo",
            "-u",
            AUDIO_USER,
            "env",
            f"XDG_RUNTIME_DIR={env['XDG_RUNTIME_DIR']}",
            *argv,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def read_system_volume() -> tuple[int, bool]:
    """Return (percent 0-100, muted)."""
    if _command_exists("wpctl"):
        proc = _run_audio_command(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])
        if proc.returncode == 0:
            text = proc.stdout.strip()
            muted = "MUTED" in text.upper()
            match = re.search(r"Volume:\s*([0-9]*\.?[0-9]+)", text, re.I)
            if match:
                return _clamp_percent(float(match.group(1)) * 100), muted

    if _command_exists("pactl"):
        proc = _run_audio_command(["pactl", "get-sink-volume", "@DEFAULT_SINK@"])
        if proc.returncode == 0:
            line = proc.stdout.splitlines()[0] if proc.stdout else ""
            muted = "muted: yes" in proc.stdout.lower()
            match = re.search(r"/\s*(\d+)", line)
            if match:
                return _clamp_percent(int(match.group(1)) / 655.35), muted

    return 0, False


def _command_exists(name: str) -> bool:
    from shutil import which

    return which(name) is not None


def _clamp_percent(value: float) -> int:
    return max(0, min(100, int(round(value))))


def touch_notify() -> tuple[int, bool]:
    global _last_notify, _last_percent, _last_muted
    percent, muted = read_system_volume()
    with _state_lock:
        _last_notify = time.monotonic()
        _last_percent = percent
        _last_muted = muted
    return percent, muted


def overlay_payload() -> dict[str, object]:
    with _state_lock:
        age = time.monotonic() - _last_notify
        visible = age <= OVERLAY_TTL_SEC and _last_notify > 0
        return {
            "visible": visible,
            "percent": _last_percent,
            "muted": _last_muted,
            "age_ms": int(age * 1000) if _last_notify else None,
        }


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write(f"koyori-audio: {self.address_string()} {fmt % args}\n")

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, code: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        path = (self.path or "").split("?", 1)[0].rstrip("/") or "/"
        if path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self._cors()
            self.end_headers()
            self.wfile.write(b"ok\n")
            return
        if path == "/volume-overlay":
            self._json(200, overlay_payload())
            return
        if path == "/volume":
            percent, muted = read_system_volume()
            self._json(200, {"percent": percent, "muted": muted})
            return
        self.send_response(404)
        self._cors()
        self.end_headers()

    def do_POST(self) -> None:
        path = (self.path or "").split("?", 1)[0].rstrip("/") or "/"
        if path == "/volume-notify":
            percent, muted = touch_notify()
            self._json(200, {"ok": True, "percent": percent, "muted": muted})
            return
        self.send_response(404)
        self._cors()
        self.end_headers()


def main() -> None:
    server = HTTPServer((HOST, PORT), _Handler)
    sys.stderr.write(f"koyori-audio: listening on http://{HOST}:{PORT}/ user={AUDIO_USER}\n")
    server.serve_forever()


if __name__ == "__main__":
    main()
