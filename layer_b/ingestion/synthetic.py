"""Generador sintético de series ambientales — solo Capa B."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from typing import Any


def _daterange(start: date, end: date) -> list[date]:
    days: list[date] = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


def _obs_id(region: str, domain: str, variable: str, day: date) -> str:
    return f"{region}_{domain}_{variable}_{day.isoformat()}"


def generate_domain_series(
    region_code: str,
    domain: str,
    variable: str,
    unit: str,
    start: date,
    end: date,
    base: float,
    amplitude: float,
    seed_offset: float = 0.0,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i, day in enumerate(_daterange(start, end)):
        seasonal = amplitude * math.sin((i + seed_offset) / 30.0)
        noise = amplitude * 0.1 * math.sin((i + seed_offset) / 7.0)
        value = base + seasonal + noise
        dt = datetime(day.year, day.month, day.day, 12, 0, 0, tzinfo=timezone.utc)
        rows.append({
            "observation_id": _obs_id(region_code, domain, variable, day),
            "region_code": region_code,
            "datetime_utc": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "domain": domain,
            "variable": variable,
            "value": round(value, 4),
            "unit": unit,
            "source": "synthetic_capa_b",
            "quality_flag": "B",
        })
    return rows


REGION_SEEDS: dict[str, float] = {
    "venezuela": 0.0,
    "colombia": 1.2,
    "ecuador": 2.1,
    "trinidad": 0.8,
    "puerto_rico": 1.5,
    "chile": 3.0,
    "california": 2.5,
    "turkey": 4.0,
    "new_zealand": 3.5,
    "japan": 4.5,
    "indonesia": 5.0,
}


def generate_connector_observations(
    connector: str,
    regions: list[str],
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    specs: dict[str, tuple[str, str, str, float, float]] = {
        "sst": ("oceanic", "sst", "degC", 27.5, 1.5),
        "pressure": ("atmospheric", "pressure_hpa", "hPa", 1013.0, 8.0),
        "rainfall": ("hydrologic", "rainfall_mm", "mm", 4.0, 12.0),
        "soil_moisture": ("hydrologic", "soil_moisture", "m3/m3", 0.35, 0.08),
        "earth_tides": ("astronomic", "earth_tide", "microstrain", 0.5, 0.2),
        "climate_indices": ("climatic", "enso_index", "index", 0.0, 1.2),
    }
    domain, variable, unit, base, amp = specs[connector]
    rows: list[dict[str, Any]] = []
    for region in regions:
        seed = REGION_SEEDS.get(region, 1.0)
        rows.extend(
            generate_domain_series(region, domain, variable, unit, start, end, base, amp, seed)
        )
    return rows
