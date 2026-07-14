#!/usr/bin/env python3
"""Near-eye JPEG HTTP for koyori (Surface Go front camera).

Phase 1 of docs/ops/koyori-near-eye.md:

  GET /latest.jpg  — last captured JPEG (may be stale)
  GET /see         — capture now, then return JPEG
  GET /health      — liveness + mtime / bytes of latest

  koyori-see-http.py --refresh   # capture into KOYORI_LATEST_JPG (timer)

Bind LAN so ma-home can pull (default 0.0.0.0:8765).
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = os.environ.get("KOYORI_SEE_HOST", "0.0.0.0")
PORT = int(os.environ.get("KOYORI_SEE_PORT", "8765"))
LATEST = Path(os.environ.get("KOYORI_LATEST_JPG", "/var/lib/koyori/latest.jpg"))
LOCK_PATH = Path(os.environ.get("KOYORI_CAPTURE_LOCK", "/var/lib/koyori/capture.lock"))
CAPTURE_BIN = os.environ.get("KOYORI_CAPTURE_BIN", "/usr/local/bin/koyori-capture")
MIN_BYTES = int(os.environ.get("KOYORI_LATEST_MIN_BYTES", "500"))

_capture_mutex = threading.Lock()


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def refresh_latest() -> Path:
    """Capture one frame under flock; atomically replace LATEST. Returns LATEST."""
    _ensure_parent(LATEST)
    _ensure_parent(LOCK_PATH)
    with _capture_mutex:
        with open(LOCK_PATH, "a+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                fd, tmp_name = tempfile.mkstemp(
                    prefix=".capture.",
                    suffix=".jpg",
                    dir=str(LATEST.parent),
                )
                os.close(fd)
                tmp_path = Path(tmp_name)
                try:
                    proc = subprocess.run(
                        [CAPTURE_BIN, str(tmp_path)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if proc.returncode != 0:
                        err = (proc.stderr or proc.stdout or "").strip()
                        raise RuntimeError(
                            f"capture failed rc={proc.returncode}: {err[:400]}"
                        )
                    size = tmp_path.stat().st_size
                    if size < MIN_BYTES:
                        raise RuntimeError(
                            f"capture too small ({size} bytes < {MIN_BYTES})"
                        )
                    os.replace(tmp_path, LATEST)
                finally:
                    if tmp_path.exists():
                        tmp_path.unlink(missing_ok=True)
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    return LATEST


def _latest_meta() -> dict[str, object]:
    if not LATEST.is_file():
        return {"exists": False, "path": str(LATEST)}
    st = LATEST.stat()
    return {
        "exists": True,
        "path": str(LATEST),
        "bytes": st.st_size,
        "mtime": st.st_mtime,
        "mtime_iso": __import__("datetime")
        .datetime.fromtimestamp(st.st_mtime)
        .astimezone()
        .isoformat(timespec="seconds"),
    }


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write(f"koyori-see-http: {self.address_string()} {fmt % args}\n")

    def _send_bytes(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, payload: dict[str, object]) -> None:
        body = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        self._send_bytes(code, body, "application/json; charset=utf-8")

    def _send_jpeg_file(self, path: Path) -> None:
        data = path.read_bytes()
        if len(data) < MIN_BYTES:
            self._send_json(
                503,
                {"ok": False, "error": "latest.jpg too small or missing"},
            )
            return
        self._send_bytes(200, data, "image/jpeg")

    def do_GET(self) -> None:
        path = (self.path or "").split("?", 1)[0].rstrip("/") or "/"

        if path == "/health":
            meta = _latest_meta()
            self._send_json(200, {"ok": True, "service": "koyori-see-http", **meta})
            return

        if path == "/latest.jpg":
            if not LATEST.is_file():
                self._send_json(404, {"ok": False, "error": "latest.jpg not found"})
                return
            self._send_jpeg_file(LATEST)
            return

        if path == "/see":
            try:
                refresh_latest()
            except Exception as exc:  # noqa: BLE001 — surface to client
                self._send_json(503, {"ok": False, "error": str(exc)})
                return
            self._send_jpeg_file(LATEST)
            return

        self._send_json(
            404,
            {
                "ok": False,
                "error": "not found",
                "routes": ["/health", "/latest.jpg", "/see"],
            },
        )


def serve() -> None:
    _ensure_parent(LATEST)
    server = ThreadingHTTPServer((HOST, PORT), _Handler)
    sys.stderr.write(
        f"koyori-see-http: listening on http://{HOST}:{PORT}/ "
        f"latest={LATEST} capture={CAPTURE_BIN}\n"
    )
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="koyori near-eye JPEG HTTP")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="capture once into KOYORI_LATEST_JPG and exit",
    )
    args = parser.parse_args()
    if args.refresh:
        out = refresh_latest()
        print(out)
        return
    serve()


if __name__ == "__main__":
    main()
