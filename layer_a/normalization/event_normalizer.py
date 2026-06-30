"""Normalización de eventos sísmicos desde distintas fuentes."""

from __future__ import annotations

from typing import Any

from layer_a.classifiers.depth import classify_depth
from layer_a.classifiers.focal_mechanism import classify_focal_mechanism
from layer_a.classifiers.magnitude import classify_magnitude
from layer_a.formatting import parse_datetime_utc
from layer_a.models import SeismicEvent


def _preferred_magnitude(mag: float, mag_type: str) -> tuple[float, str]:
    mag_type_upper = mag_type.upper()
    if mag_type_upper in {"MW", "Mww", "Mwc"}:
        return mag, "high"
    if mag_type_upper in {"ML", "MB", "MS", "MD"}:
        return mag, "medium"
    return mag, "low"


def normalize_raw_event(raw: dict[str, Any], source: str) -> SeismicEvent:
    mag = float(raw["magnitude"])
    mag_type = str(raw.get("magnitude_type", "unknown"))
    preferred, quality = _preferred_magnitude(mag, mag_type)
    depth = float(raw["depth_km"])
    rake = raw.get("rake")
    rake_val = float(rake) if rake is not None else None

    event = SeismicEvent(
        event_id=str(raw["event_id"]),
        source=source,
        source_event_id=str(raw.get("source_event_id", raw["event_id"])),
        datetime_utc=parse_datetime_utc(str(raw["datetime_utc"])),
        latitude=float(raw["latitude"]),
        longitude=float(raw["longitude"]),
        depth_km=depth,
        magnitude=mag,
        magnitude_type=mag_type,
        place=str(raw.get("place", "")),
        status=str(raw.get("status", "reviewed")),
        location_uncertainty_km=raw.get("location_uncertainty_km"),
        depth_uncertainty_km=raw.get("depth_uncertainty_km"),
        magnitude_uncertainty=raw.get("magnitude_uncertainty"),
        magnitude_preferred=preferred,
        magnitude_quality=quality,
        strike=raw.get("strike"),
        dip=raw.get("dip"),
        rake=rake_val,
        moment_tensor_available=bool(raw.get("moment_tensor_available", False)),
        focal_mechanism_type=classify_focal_mechanism(rake_val),
        depth_class=classify_depth(depth),
        magnitude_class=classify_magnitude(preferred),
    )
    return event


def normalize_catalog(raw_events: list[dict[str, Any]], source: str) -> list[SeismicEvent]:
    return [normalize_raw_event(item, source) for item in raw_events]
