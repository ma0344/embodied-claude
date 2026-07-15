"""JMA weather API client for WS-5b (Nagano / Matsumoto).

Region codes (hardcoded allowlist, verified from JMA):
- office (府県予報区): 200000 長野県
- class10 (一次細分・中部): 200020
- AMeDAS / temp point: 48361 松本
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

# Matsumoto / Nagano — hardcoded allowlist
JMA_OFFICE_NAGANO = "200000"
JMA_CLASS10_CHUBU = "200020"  # 中部（松本含む）
JMA_AMEDAS_MATSUMOTO = "48361"
JMA_FORECAST_URL = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{JMA_OFFICE_NAGANO}.json"


@dataclass(frozen=True, slots=True)
class WeatherSnapshot:
    region_label: str
    weather_text: str
    temp_min: str | None
    temp_max: str | None
    report_datetime: str
    source_url: str


def _area_code(area_obj: dict[str, Any]) -> str:
    area = area_obj.get("area") or {}
    return str(area.get("code") or "")


def _pick_class10_weather(series_list: list[Any]) -> str:
    for series in series_list:
        if not isinstance(series, dict):
            continue
        areas = series.get("areas") or []
        for row in areas:
            if not isinstance(row, dict):
                continue
            if _area_code(row) != JMA_CLASS10_CHUBU:
                continue
            weathers = row.get("weathers") or []
            if weathers:
                text = str(weathers[0]).replace("　", "").strip()
                if text:
                    return text
    return ""


def _pick_matsumoto_temps(series_list: list[Any]) -> tuple[str | None, str | None]:
    for series in series_list:
        if not isinstance(series, dict):
            continue
        areas = series.get("areas") or []
        for row in areas:
            if not isinstance(row, dict):
                continue
            if _area_code(row) != JMA_AMEDAS_MATSUMOTO:
                continue
            temps = row.get("temps") or []
            if len(temps) >= 2:
                lo = str(temps[0]).strip() or None
                hi = str(temps[1]).strip() or None
                return lo, hi
            if len(temps) == 1:
                only = str(temps[0]).strip() or None
                return only, only
    return None, None


def parse_jma_forecast_json(
    payload: Any,
    *,
    region_label: str = "松本",
) -> WeatherSnapshot | None:
    """Extract 松本 temps (48361) + 中部 weather (200020) from office forecast JSON."""
    if not isinstance(payload, list) or not payload:
        return None
    first = payload[0]
    if not isinstance(first, dict):
        return None
    series_list = first.get("timeSeries") or []
    if not isinstance(series_list, list):
        return None
    weather_text = _pick_class10_weather(series_list)
    temp_min, temp_max = _pick_matsumoto_temps(series_list)
    if not weather_text and temp_min is None and temp_max is None:
        return None
    report = str(first.get("reportDatetime") or "").strip()
    return WeatherSnapshot(
        region_label=region_label,
        weather_text=weather_text,
        temp_min=temp_min,
        temp_max=temp_max,
        report_datetime=report,
        source_url=JMA_FORECAST_URL,
    )


def format_weather_answer(
    snap: WeatherSnapshot,
    *,
    used_default_region: bool,
) -> str:
    """Deterministic answer line for [web_search_prefetch] — LM must not invent numbers."""
    label = f"{snap.region_label}（前提・地域未指定）" if used_default_region else snap.region_label
    parts: list[str] = [label]
    if snap.temp_min and snap.temp_max and snap.temp_min != snap.temp_max:
        parts.append(f"気温 最低{snap.temp_min}℃ / 最高{snap.temp_max}℃")
    elif snap.temp_max:
        parts.append(f"気温 約{snap.temp_max}℃")
    elif snap.temp_min:
        parts.append(f"気温 約{snap.temp_min}℃")
    if snap.weather_text:
        parts.append(f"天気:{snap.weather_text}")
    if snap.report_datetime:
        parts.append(f"発表:{snap.report_datetime}")
    return " · ".join(parts)


async def fetch_jma_matsumoto_weather(
    *,
    region_label: str = "松本",
    timeout_sec: float = 8.0,
) -> WeatherSnapshot | None:
    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            resp = await client.get(JMA_FORECAST_URL)
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, ValueError, TypeError):
        return None
    return parse_jma_forecast_json(payload, region_label=region_label)
