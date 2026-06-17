"""Best-effort HTTP push when outbound nudges enqueue (A4g — ntfy / Pushover)."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


def outbound_push_enabled() -> bool:
    return os.getenv("PRESENCE_OUTBOUND_PUSH", "1").lower() not in {"0", "false", "no"}


def _ntfy_url() -> str:
    return os.getenv("PRESENCE_OUTBOUND_NTFY_URL", "").strip()


def _pushover_credentials() -> tuple[str, str]:
    return (
        os.getenv("PRESENCE_OUTBOUND_PUSHOVER_TOKEN", "").strip(),
        os.getenv("PRESENCE_OUTBOUND_PUSHOVER_USER", "").strip(),
    )


def _post_json(url: str, payload: dict[str, Any], *, timeout: float = 8.0) -> None:
    import json

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        if response.status >= 400:
            raise HTTPError(url, response.status, response.reason, response.headers, None)


def _ntfy_click_url() -> str:
    explicit = os.getenv("PRESENCE_OUTBOUND_NTFY_CLICK_URL", "").strip()
    if explicit:
        return explicit
    base = os.getenv("PRESENCE_BASE_URL", "http://127.0.0.1:8090").strip().rstrip("/")
    if not base:
        return "http://127.0.0.1:8090/"
    return f"{base}/"


def _win_toast_enabled() -> bool:
    """Win toast when 8090 tab is closed. Default on for Windows (may duplicate browser toast)."""
    val = os.getenv("PRESENCE_OUTBOUND_WIN_TOAST", "auto").strip().lower()
    if val in {"0", "false", "no"}:
        return False
    if val in {"1", "true", "yes", "auto"}:
        return sys.platform == "win32"
    return sys.platform == "win32"


def _win_toast_script() -> Path | None:
    explicit = os.getenv("PRESENCE_OUTBOUND_WIN_TOAST_SCRIPT", "").strip()
    if explicit:
        path = Path(explicit)
        return path if path.is_file() else None
    for root in (
        os.getenv("EMBODIED_CLAUDE_ROOT", "").strip(),
        os.getenv("PRESENCE_PROJECT_PATH", "").strip(),
    ):
        if not root:
            continue
        path = Path(root) / "scripts" / "show-koyori-win-toast.ps1"
        if path.is_file():
            return path
    path = Path(__file__).resolve().parents[4] / "scripts" / "show-koyori-win-toast.ps1"
    return path if path.is_file() else None


def _subprocess_no_window_kwargs() -> dict[str, int]:
    if sys.platform != "win32":
        return {}
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if not flags:
        return {}
    return {"creationflags": flags}


def _show_win_toast(*, title: str, message: str, click_url: str) -> None:
    script = _win_toast_script()
    if not script:
        raise FileNotFoundError("show-koyori-win-toast.ps1 not found")
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-Title",
            title,
            "-Message",
            message,
            "-ClickUrl",
            click_url,
        ],
        check=False,
        timeout=15,
        capture_output=True,
        text=True,
        **_subprocess_no_window_kwargs(),
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip() or f"exit {completed.returncode}"
        raise RuntimeError(detail)


def _post_ntfy(
    url: str,
    *,
    title: str,
    message: str,
    click_url: str | None = None,
    timeout: float = 8.0,
) -> None:
    body = message.encode("utf-8")
    # HTTP header values must be ASCII for urllib; ntfy title supports UTF-8 via body fallback.
    safe_title = title.encode("ascii", "backslashreplace").decode("ascii")
    headers = {
        "Title": safe_title,
        "Priority": "3",
        "Tags": "koyori,outbound",
        "Content-Type": "text/plain; charset=utf-8",
    }
    if click_url:
        headers["Click"] = click_url
    request = Request(
        url,
        data=body,
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        if response.status >= 400:
            raise HTTPError(url, response.status, response.reason, response.headers, None)


def send_outbound_push(
    *,
    text: str,
    title: str = "Koyori",
    include_pc_local: bool = True,
) -> tuple[bool, str]:
    """Fire configured push backends. Returns (any_ok, detail)."""
    if not outbound_push_enabled():
        return False, "push disabled"

    line = text.strip()
    if not line:
        return False, "empty text"

    ntfy = _ntfy_url()
    pushover_token, pushover_user = _pushover_credentials()
    win_toast = include_pc_local and _win_toast_enabled() and _win_toast_script() is not None
    if not ntfy and not (pushover_token and pushover_user) and not win_toast:
        return False, "no push targets configured"

    results: list[str] = []
    ok_any = False
    click_url = _ntfy_click_url()

    if win_toast:
        try:
            _show_win_toast(title=title, message=line, click_url=click_url)
            ok_any = True
            results.append("win-toast:ok")
        except (TimeoutError, OSError, RuntimeError, FileNotFoundError) as exc:
            logger.warning("outbound win toast failed: %s", exc)
            results.append(f"win-toast:{exc}")

    if ntfy:
        try:
            _post_ntfy(ntfy, title=title, message=line, click_url=click_url)
            ok_any = True
            results.append("ntfy:ok")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            logger.warning("outbound ntfy push failed: %s", exc)
            results.append(f"ntfy:{exc}")

    if pushover_token and pushover_user:
        try:
            payload: dict[str, Any] = {
                "token": pushover_token,
                "user": pushover_user,
                "title": title,
                "message": line,
                "priority": 0,
            }
            click_url = _ntfy_click_url()
            if click_url:
                payload["url"] = click_url
                payload["url_title"] = "Koyori room"
            _post_json(
                "https://api.pushover.net/1/messages.json",
                payload,
            )
            ok_any = True
            results.append("pushover:ok")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            logger.warning("outbound pushover push failed: %s", exc)
            results.append(f"pushover:{exc}")

    return ok_any, "; ".join(results)
