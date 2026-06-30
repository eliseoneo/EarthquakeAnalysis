"""Detección de dobletes y multipletes."""

from __future__ import annotations

from typing import Any

from layer_a.geo.distance import haversine_km
from layer_a.models import DoubletCandidate, SeismicEvent


def _classify_doublet(
    time_delta_hours: float,
    distance_km: float,
    magnitude_delta: float,
    cfg: dict[str, Any],
) -> str:
    strict = (
        time_delta_hours <= cfg["strict_time_delta_hours"]
        and distance_km <= cfg["strict_distance_km"]
        and magnitude_delta <= cfg.get("strict_magnitude_delta", 0.3)
    )
    if strict:
        return "high_confidence_doublet"
    if (
        time_delta_hours <= cfg["max_time_delta_hours"]
        and distance_km <= cfg["max_distance_km"]
        and magnitude_delta <= cfg["max_magnitude_delta"]
    ):
        return "possible_doublet"
    return "catalog_uncertainty"


def detect_doublets(
    catalog: list[SeismicEvent],
    cfg: dict[str, Any],
) -> list[DoubletCandidate]:
    min_mag = cfg["min_magnitude"]
    candidates: list[DoubletCandidate] = []
    majors = [e for e in catalog if e.magnitude >= min_mag]
    majors.sort(key=lambda e: e.datetime_utc)

    for i, a in enumerate(majors):
        for b in majors[i + 1 :]:
            time_delta = abs((b.datetime_utc - a.datetime_utc).total_seconds())
            time_hours = time_delta / 3600
            if time_hours > cfg["max_time_delta_hours"]:
                break
            distance = haversine_km(a.latitude, a.longitude, b.latitude, b.longitude)
            mag_delta = abs(a.magnitude - b.magnitude)
            depth_delta = abs(a.depth_km - b.depth_km)
            classification = _classify_doublet(time_hours, distance, mag_delta, cfg)
            if classification == "catalog_uncertainty":
                continue
            same_fault = (
                a.fault_system is not None
                and a.fault_system == b.fault_system
            )
            same_fm = (
                a.focal_mechanism_type is not None
                and a.focal_mechanism_type == b.focal_mechanism_type
                and a.focal_mechanism_type != "unknown"
            )
            confidence = "A" if classification == "high_confidence_doublet" else "B"
            candidates.append(
                DoubletCandidate(
                    doublet_id=f"doublet_{a.event_id}_{b.event_id}",
                    event_id_1=a.event_id,
                    event_id_2=b.event_id,
                    time_delta_seconds=time_delta,
                    distance_km=distance,
                    magnitude_delta=mag_delta,
                    depth_delta_km=depth_delta,
                    same_fault_system=same_fault,
                    same_focal_mechanism_type=same_fm,
                    confidence_level=confidence,
                    classification=classification,
                )
            )
    return candidates
