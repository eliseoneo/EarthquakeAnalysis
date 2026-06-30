"""Carga de series desde raw, fixtures o generador sintético."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from layer_b.ingestion.synthetic import generate_connector_observations
from layer_b.paths import FIXTURES_DIR, RAW_DIR


def load_connector_raw(
    connector: str,
    *,
    regions: list[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    use_synthetic_fallback: bool = True,
) -> list[dict[str, Any]]:
    raw_path = RAW_DIR / f"{connector}.json"
    if raw_path.exists():
        data = json.loads(raw_path.read_text(encoding="utf-8"))
        return data.get("observations", data if isinstance(data, list) else [])

    fixture_path = FIXTURES_DIR / f"{connector}_sample.json"
    if fixture_path.exists():
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        return data.get("observations", [])

    if use_synthetic_fallback and regions and start_date and end_date:
        return generate_connector_observations(connector, regions, start_date, end_date)
    return []
