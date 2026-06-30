"""Detección de réplicas."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from layer_a.geo.distance import haversine_km
from layer_a.models import AftershockSequence, SeismicEvent


def detect_aftershocks(
    mainshock: SeismicEvent,
    catalog: list[SeismicEvent],
    time_window_days: int = 365,
    radius_km: float = 250,
    extended_radius_km: float = 500,
) -> tuple[list[SeismicEvent], AftershockSequence]:
    aftershocks: list[SeismicEvent] = []
    end = mainshock.datetime_utc + timedelta(days=time_window_days)

    for event in catalog:
        if event.event_id == mainshock.event_id:
            continue
        if event.datetime_utc <= mainshock.datetime_utc or event.datetime_utc > end:
            continue
        dist = haversine_km(
            mainshock.latitude, mainshock.longitude,
            event.latitude, event.longitude,
        )
        use_radius = radius_km if event.magnitude >= 4.0 else extended_radius_km
        if dist > use_radius:
            continue
        if event.magnitude > mainshock.magnitude:
            continue
        tagged = event.model_copy(
            update={
                "is_aftershock": True,
                "sequence_id": mainshock.event_id,
                "confidence_level": "A" if dist <= radius_km else "B",
            }
        )
        aftershocks.append(tagged)

    def count_within(days: int) -> int:
        cutoff = mainshock.datetime_utc + timedelta(days=days)
        return sum(1 for e in aftershocks if e.datetime_utc <= cutoff)

    depths = [e.depth_km for e in aftershocks]
    mags = [e.magnitude for e in aftershocks]
    distances = [
        haversine_km(mainshock.latitude, mainshock.longitude, e.latitude, e.longitude)
        for e in aftershocks
    ]

    sequence = AftershockSequence(
        mainshock_id=mainshock.event_id,
        aftershock_ids=[e.event_id for e in aftershocks],
        aftershock_count_3d=count_within(3),
        aftershock_count_7d=count_within(7),
        aftershock_count_30d=count_within(30),
        aftershock_count_90d=count_within(90),
        aftershock_count_365d=count_within(365),
        max_aftershock_magnitude=max(mags) if mags else None,
        mean_aftershock_depth=sum(depths) / len(depths) if depths else None,
        spatial_dispersion_km=max(distances) if distances else None,
    )
    return aftershocks, sequence


def apply_aftershock_metrics(
    mainshock: SeismicEvent,
    sequence: AftershockSequence,
) -> SeismicEvent:
    return mainshock.model_copy(
        update={
            "aftershock_count_3d": sequence.aftershock_count_3d,
            "aftershock_count_7d": sequence.aftershock_count_7d,
            "aftershock_count_30d": sequence.aftershock_count_30d,
        }
    )
