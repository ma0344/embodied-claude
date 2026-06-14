"""HTTP sidecar helpers: health probe, stale listener reclaim."""

from __future__ import annotations

import logging
import subprocess
import sys
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

_ADDR_IN_USE_ERRNOS = {98, 10048}  # EADDRINUSE (Unix / Windows)


def is_address_in_use(exc: OSError) -> bool:
    if exc.errno in _ADDR_IN_USE_ERRNOS:
        return True
    return "Address already in use" in str(exc) or "通常、各ソケット" in str(exc)


def find_listening_pid(port: int, host: str = "127.0.0.1") -> int | None:
    """Return PID listening on host:port, or None."""
    needle = f"{host}:{port}"
    try:
        if sys.platform == "win32":
            out = subprocess.check_output(
                ["netstat", "-ano"],
                text=True,
                errors="replace",
                timeout=5,
            )
            for line in out.splitlines():
                if "LISTENING" not in line or needle not in line:
                    continue
                parts = line.split()
                if parts and parts[-1].isdigit():
                    return int(parts[-1])
            return None

        out = subprocess.check_output(
            ["ss", "-ltnp"],
            text=True,
            errors="replace",
            timeout=5,
        )
        for line in out.splitlines():
            if needle not in line:
                continue
            if "pid=" in line:
                fragment = line.split("pid=", 1)[1]
                pid_str = fragment.split(",", 1)[0]
                if pid_str.isdigit():
                    return int(pid_str)
        return None
    except (subprocess.SubprocessError, OSError, ValueError):
        return None


def probe_health(port: int, *, timeout_sec: float = 2.0, host: str = "127.0.0.1") -> bool:
    """True when GET /health returns HTTP 200 with ok=true."""
    url = f"http://{host}:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout_sec) as resp:
            if resp.status != 200:
                return False
            body = resp.read().decode("utf-8", errors="replace")
            return '"ok": true' in body.replace(" ", "") or '"ok":true' in body.replace(" ", "")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False


def kill_process_tree(pid: int) -> bool:
    """Force-kill a process tree. Returns True if kill was attempted."""
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            proc = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return proc.returncode == 0
        proc = subprocess.run(
            ["kill", "-9", str(pid)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return proc.returncode == 0
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("Failed to kill PID %s: %s", pid, exc)
        return False


def reclaim_stale_listener(
    port: int,
    *,
    host: str = "127.0.0.1",
    health_timeout_sec: float = 2.0,
) -> bool:
    """Kill the listener on port when /health is missing or unresponsive."""
    pid = find_listening_pid(port, host=host)
    if pid is None:
        return False
    if probe_health(port, timeout_sec=health_timeout_sec, host=host):
        logger.info(
            "Port %s:%s is owned by healthy peer PID %s; leaving it",
            host,
            port,
            pid,
        )
        return False
    logger.warning(
        "Reclaiming stale memory HTTP listener PID %s on %s:%s (health probe failed)",
        pid,
        host,
        port,
    )
    return kill_process_tree(pid)
