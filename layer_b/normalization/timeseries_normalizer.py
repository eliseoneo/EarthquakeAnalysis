"""Normalización de observaciones ambientales."""

from __future__ import annotations

from typing import Any

from layer_b.formatting import parse_datetime_utc
from layer_b.models import EnvironmentalObservation


def normalize_observation(raw: dict[str, Any]) -> EnvironmentalObservation:
    return EnvironmentalObservation(
        observation_id=str(raw["observation_id"]),
        region_code=str(raw["region_code"]),
        datetime_utc=parse_datetime_utc(str(raw["datetime_utc"])),
        domain=str(raw["domain"]),
        variable=str(raw["variable"]),
        value=float(raw["value"]),
        unit=str(raw.get("unit", "")),
        source=str(raw.get("source", "synthetic")),
        quality_flag=str(raw.get("quality_flag", "B")),
    )


def normalize_observations(rows: list[dict[str, Any]]) -> list[EnvironmentalObservation]:
    return [normalize_observation(row) for row in rows]
