"""Ventanas temporales alrededor de mainshocks."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from layer_a.geo.distance import haversine_km
from layer_a.models import SeismicEvent
from layer_a.tectonic.b_value import calculate_b_value


def build_temporal_windows(
    mainshock: SeismicEvent,
    catalog: list[SeismicEvent],
    window_days: list[int],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for offset in window_days:
        start = mainshock.datetime_utc + timedelta(days=offset)
        if offset < 0:
            end = mainshock.datetime_utc
            in_window = [
                e for e in catalog
                if start <= e.datetime_utc < end and e.event_id != mainshock.event_id
            ]
        elif offset == 0:
            in_window = [mainshock]
        else:
            end = mainshock.datetime_utc + timedelta(days=offset)
            in_window = [
                e for e in catalog
                if mainshock.datetime_utc < e.datetime_utc <= end
                and e.event_id != mainshock.event_id
            ]

        mags = [e.magnitude for e in in_window]
        depths = [e.depth_km for e in in_window]
        distances = [
            haversine_km(mainshock.latitude, mainshock.longitude, e.latitude, e.longitude)
            for e in in_window
        ]
        b_result = calculate_b_value(in_window)

        rows.append({
            "mainshock_id": mainshock.event_id,
            "window_offset_days": offset,
            "event_count": len(in_window),
            "max_magnitude": max(mags) if mags else None,
            "mean_magnitude": sum(mags) / len(mags) if mags else None,
            "median_depth_km": sorted(depths)[len(depths) // 2] if depths else None,
            "mean_depth_km": sum(depths) / len(depths) if depths else None,
            "min_distance_to_mainshock_km": min(distances) if distances else None,
            "max_distance_to_mainshock_km": max(distances) if distances else None,
            "b_value": b_result.b_value,
            "b_value_confidence": b_result.confidence_level,
        })
    return rows
