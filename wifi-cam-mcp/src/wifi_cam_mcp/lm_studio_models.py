"""LM Studio native v1 API — vision model unload/reload on corrupt output."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from .vision import _lm_auth_headers, lm_studio_settings

logger = logging.getLogger(__name__)

_last_vision_reload_monotonic: float = 0.0


def vision_auto_reload_enabled() -> bool:
    raw = os.environ.get("WIFI_CAM_VISION_AUTO_RELOAD", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def vision_reload_cooldown_sec() -> float:
    return float(os.environ.get("WIFI_CAM_VISION_RELOAD_COOLDOWN_SEC", "300"))


def vision_reload_wait_sec() -> float:
    return float(os.environ.get("WIFI_CAM_VISION_RELOAD_WAIT_SEC", "3"))


def vision_context_length() -> int:
    return int(os.environ.get("WIFI_CAM_VISION_CONTEXT_LENGTH", "8192"))


def _normalize_model_id(model_id: str) -> str:
    return model_id.strip().lower().replace("\\", "/")


def model_ids_match(a: str, b: str) -> bool:
    """Match env id with LM Studio list key / instance id (suffix-tolerant)."""
    na, nb = _normalize_model_id(a), _normalize_model_id(b)
    if na == nb:
        return True
    if na.endswith(f"/{nb}") or nb.endswith(f"/{na}"):
        return True
    return na.rsplit("/", 1)[-1] == nb.rsplit("/", 1)[-1]


def find_model_entry(models: list[dict[str, Any]], model_id: str) -> dict[str, Any] | None:
    for entry in models:
        key = str(entry.get("key") or "")
        if model_ids_match(key, model_id):
            return entry
        for inst in entry.get("loaded_instances") or []:
            inst_id = str(inst.get("id") or "")
            if inst_id and model_ids_match(inst_id, model_id):
                return entry
        for variant in entry.get("variants") or []:
            if model_ids_match(str(variant), model_id):
                return entry
    return None


def reload_cooldown_allows() -> bool:
    global _last_vision_reload_monotonic
    elapsed = time.monotonic() - _last_vision_reload_monotonic
    return elapsed >= vision_reload_cooldown_sec()


def mark_reload_done() -> None:
    global _last_vision_reload_monotonic
    _last_vision_reload_monotonic = time.monotonic()


async def unload_vision_model(
    client: httpx.AsyncClient,
    *,
    base: str,
    token: str,
    model_id: str,
) -> int:
    """Unload all loaded instances for model_id. Returns count unloaded."""
    headers = _lm_auth_headers(token)
    try:
        resp = await client.get(f"{base}/api/v1/models", headers=headers)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("LM Studio list models failed during unload: %s", exc)
        return 0

    payload = resp.json()
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return 0

    entry = find_model_entry(models, model_id)
    if not entry:
        return 0

    unloaded = 0
    for inst in entry.get("loaded_instances") or []:
        inst_id = str(inst.get("id") or "").strip()
        if not inst_id:
            continue
        try:
            uresp = await client.post(
                f"{base}/api/v1/models/unload",
                headers=headers,
                json={"instance_id": inst_id},
            )
            uresp.raise_for_status()
            unloaded += 1
            logger.info("Unloaded vision instance %s", inst_id)
        except Exception as exc:
            logger.warning("Unload %s failed: %s", inst_id, exc)
    return unloaded


async def reload_vision_model(
    client: httpx.AsyncClient,
    *,
    base: str,
    token: str,
    model_id: str,
    force: bool = False,
) -> bool:
    """Unload then reload the vision model via POST /api/v1/models/*."""
    if not force and not reload_cooldown_allows():
        logger.info(
            "Vision model reload skipped (cooldown %.0fs)",
            vision_reload_cooldown_sec(),
        )
        return False

    headers = _lm_auth_headers(token)
    list_url = f"{base}/api/v1/models"
    try:
        resp = await client.get(list_url, headers=headers)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("LM Studio list models failed (%s): %s", list_url, exc)
        return False

    payload = resp.json()
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        logger.warning("LM Studio list models: unexpected payload")
        return False

    entry = find_model_entry(models, model_id)
    load_key = str(entry.get("key") if entry else model_id)
    context_length = vision_context_length()
    if entry:
        instances = entry.get("loaded_instances") or []
        if instances:
            cfg = instances[0].get("config") or {}
            if isinstance(cfg.get("context_length"), int):
                context_length = int(cfg["context_length"])

    unloaded = 0
    if entry:
        for inst in entry.get("loaded_instances") or []:
            inst_id = str(inst.get("id") or "").strip()
            if not inst_id:
                continue
            try:
                uresp = await client.post(
                    f"{base}/api/v1/models/unload",
                    headers=headers,
                    json={"instance_id": inst_id},
                )
                uresp.raise_for_status()
                unloaded += 1
                logger.info("Unloaded vision instance %s", inst_id)
            except Exception as exc:
                logger.warning("Unload %s failed: %s", inst_id, exc)

    load_body: dict[str, Any] = {
        "model": load_key,
        "context_length": context_length,
    }
    try:
        lresp = await client.post(
            f"{base}/api/v1/models/load",
            headers=headers,
            json=load_body,
        )
        lresp.raise_for_status()
    except Exception as exc:
        logger.warning("LM Studio load %s failed: %s", load_key, exc)
        return False

    mark_reload_done()
    wait = vision_reload_wait_sec()
    if wait > 0:
        import asyncio

        await asyncio.sleep(wait)
    logger.info(
        "Reloaded vision model %s (unloaded %d instance(s), ctx=%d)",
        load_key,
        unloaded,
        context_length,
    )
    return True


async def prepare_isolated_vision_model(
    client: httpx.AsyncClient,
    *,
    base: str,
    token: str,
    model_id: str,
    other_model_ids: list[str] | None = None,
) -> bool:
    """Unload peers then reload target — fair A/B on one GPU."""
    for other in other_model_ids or []:
        if not model_ids_match(other, model_id):
            await unload_vision_model(client, base=base, token=token, model_id=other)
    return await reload_vision_model(
        client, base=base, token=token, model_id=model_id, force=True
    )


async def reload_configured_vision_model(client: httpx.AsyncClient) -> bool:
    base, model, token = lm_studio_settings()
    return await reload_vision_model(client, base=base, token=token, model_id=model)
