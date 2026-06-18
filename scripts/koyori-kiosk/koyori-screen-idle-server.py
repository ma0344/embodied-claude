#!/usr/bin/env python3
"""Localhost HTTP helper: force X11 display off/on for kiosk idle sleep (C11g)."""

from __future__ import annotations

import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = os.environ.get("KOYORI_SCREEN_IDLE_HOST", "127.0.0.1")
PORT = int(os.environ.get("KOYORI_SCREEN_IDLE_PORT", "18790"))


def _xset(*args: str) -> None:
    env = os.environ.copy()
    if not env.get("DISPLAY"):
        return
    subprocess.run(["xset", *args], env=env, check=False, capture_output=True)


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write(f"koyori-screen-idle: {self.address_string()} {fmt % args}\n")

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        path = (self.path or "").split("?", 1)[0].rstrip("/") or "/"
        if path == "/screen-off":
            _xset("dpms", "force", "off")
            self.send_response(204)
        elif path == "/screen-on":
            _xset("dpms", "force", "on")
            _xset("s", "reset")
            self.send_response(204)
        elif path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self._cors()
            self.end_headers()
            self.wfile.write(b"ok\n")
            return
        else:
            self.send_response(404)
        self._cors()
        self.end_headers()


def main() -> None:
    if not os.environ.get("DISPLAY"):
        sys.stderr.write("koyori-screen-idle: DISPLAY unset — exit\n")
        sys.exit(1)
    server = HTTPServer((HOST, PORT), _Handler)
    sys.stderr.write(f"koyori-screen-idle: listening on http://{HOST}:{PORT}/\n")
    server.serve_forever()


if __name__ == "__main__":
    main()
