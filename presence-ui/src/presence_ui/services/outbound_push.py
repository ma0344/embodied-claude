"""Best-effort HTTP push when outbound nudges enqueue (A4g — ntfy / Pushover)."""

from __future__ import annotations

import logging
import os
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


def _post_ntfy(url: str, *, title: str, message: str, timeout: float = 8.0) -> None:
    body = message.encode("utf-8")
    # HTTP header values must be ASCII for urllib; ntfy title supports UTF-8 via body fallback.
    safe_title = title.encode("ascii", "backslashreplace").decode("ascii")
    request = Request(
        url,
        data=body,
        headers={
            "Title": safe_title,
            "Priority": "3",
            "Tags": "koyori,outbound",
            "Content-Type": "text/plain; charset=utf-8",
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        if response.status >= 400:
            raise HTTPError(url, response.status, response.reason, response.headers, None)


def send_outbound_push(*, text: str, title: str = "Koyori") -> tuple[bool, str]:
    """Fire configured push backends. Returns (any_ok, detail)."""
    if not outbound_push_enabled():
        return False, "push disabled"

    line = text.strip()
    if not line:
        return False, "empty text"

    ntfy = _ntfy_url()
    pushover_token, pushover_user = _pushover_credentials()
    if not ntfy and not (pushover_token and pushover_user):
        return False, "no push targets configured"

    results: list[str] = []
    ok_any = False

    if ntfy:
        try:
            _post_ntfy(ntfy, title=title, message=line)
            ok_any = True
            results.append("ntfy:ok")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            logger.warning("outbound ntfy push failed: %s", exc)
            results.append(f"ntfy:{exc}")

    if pushover_token and pushover_user:
        try:
            _post_json(
                "https://api.pushover.net/1/messages.json",
                {
                    "token": pushover_token,
                    "user": pushover_user,
                    "title": title,
                    "message": line,
                    "priority": 0,
                },
            )
            ok_any = True
            results.append("pushover:ok")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            logger.warning("outbound pushover push failed: %s", exc)
            results.append(f"pushover:{exc}")

    return ok_any, "; ".join(results)
