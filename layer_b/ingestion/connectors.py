"""Conectores de dominio — Capa B."""

from __future__ import annotations

from datetime import date
from typing import Any

from layer_b.ingestion.loader import load_connector_raw


def _load(name: str, regions: list[str], start: date, end: date) -> list[dict[str, Any]]:
    return load_connector_raw(
        name,
        regions=regions,
        start_date=start,
        end_date=end,
        use_synthetic_fallback=True,
    )


def load_sst(regions: list[str], start: date, end: date) -> list[dict[str, Any]]:
    return _load("sst", regions, start, end)


def load_pressure(regions: list[str], start: date, end: date) -> list[dict[str, Any]]:
    return _load("pressure", regions, start, end)


def load_rainfall(regions: list[str], start: date, end: date) -> list[dict[str, Any]]:
    return _load("rainfall", regions, start, end)


def load_soil_moisture(regions: list[str], start: date, end: date) -> list[dict[str, Any]]:
    return _load("soil_moisture", regions, start, end)


def load_earth_tides(regions: list[str], start: date, end: date) -> list[dict[str, Any]]:
    return _load("earth_tides", regions, start, end)


def load_climate_indices(regions: list[str], start: date, end: date) -> list[dict[str, Any]]:
    return _load("climate_indices", regions, start, end)


CONNECTORS = {
    "sst": load_sst,
    "pressure": load_pressure,
    "rainfall": load_rainfall,
    "soil_moisture": load_soil_moisture,
    "earth_tides": load_earth_tides,
    "climate_indices": load_climate_indices,
}


def load_all_connectors(names: list[str], regions: list[str], start: date, end: date) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in names:
        loader = CONNECTORS.get(name)
        if loader:
            rows.extend(loader(regions, start, end))
    return rows
