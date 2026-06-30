"""Índices tectónicos interpretables."""

from __future__ import annotations

from layer_a.models import SeismicEvent, TectonicIndexRecord


def _activity_level(recent_count: int, max_mag: float) -> str:
    score = recent_count + max_mag * 2
    if score >= 25:
        return "very_high"
    if score >= 15:
        return "high"
    if score >= 8:
        return "medium"
    return "low"


def _fault_proximity(distance_km: float | None) -> str:
    if distance_km is None:
        return "medium"
    if distance_km <= 10:
        return "very_high"
    if distance_km <= 25:
        return "high"
    if distance_km <= 50:
        return "medium"
    return "low"


def _aftershock_rate(observed: int, expected_ratio: float | None) -> str:
    if expected_ratio is None:
        return "medium" if observed >= 5 else "low"
    if expected_ratio >= 1.5:
        return "very_high"
    if expected_ratio >= 1.0:
        return "high"
    if expected_ratio >= 0.5:
        return "medium"
    return "low"


def _depth_risk(depth_km: float, magnitude: float) -> str:
    if depth_km <= 30 and magnitude >= 6.0:
        return "very_high"
    if depth_km <= 30:
        return "high"
    if depth_km <= 70:
        return "medium"
    return "low"


def _magnitude_energy(magnitude: float) -> str:
    if magnitude >= 7.0:
        return "very_high"
    if magnitude >= 6.0:
        return "high"
    if magnitude >= 5.0:
        return "medium"
    return "low"


def compute_tectonic_indexes(
    event: SeismicEvent,
    recent_events: list[SeismicEvent],
    omori_ratio: float | None = None,
) -> TectonicIndexRecord:
    recent_count = len(recent_events)
    max_mag = max((e.magnitude for e in recent_events), default=event.magnitude)
    aftershocks = event.aftershock_count_30d or 0

    return TectonicIndexRecord(
        event_id=event.event_id,
        tectonic_activity_index=_activity_level(recent_count, max_mag),
        fault_proximity_index=_fault_proximity(event.distance_to_nearest_fault_km),
        aftershock_rate_index=_aftershock_rate(aftershocks, omori_ratio),
        depth_risk_index=_depth_risk(event.depth_km, event.magnitude),
        magnitude_energy_index=_magnitude_energy(event.magnitude),
        evidence_level="A" if event.confidence_level == "A" else "B",
    )
