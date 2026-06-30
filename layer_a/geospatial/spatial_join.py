"""Asociación espacial con fallas y límites de placas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from layer_a.geo.distance import haversine_km
from layer_a.models import SeismicEvent


def _load_geojson_points(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    features = data.get("features", [])
    points: list[dict[str, Any]] = []
    for feature in features:
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        if geom.get("type") == "Point":
            lon, lat = geom["coordinates"][:2]
            points.append({"lat": lat, "lon": lon, **props})
    return points


def associate_faults_and_plates(
    events: list[SeismicEvent],
    faults_path: Path,
    plates_path: Path,
) -> list[SeismicEvent]:
    faults = _load_geojson_points(faults_path)
    plates = _load_geojson_points(plates_path)
    enriched: list[SeismicEvent] = []

    for event in events:
        nearest_fault = None
        nearest_fault_dist = float("inf")
        for fault in faults:
            dist = haversine_km(event.latitude, event.longitude, fault["lat"], fault["lon"])
            if dist < nearest_fault_dist:
                nearest_fault_dist = dist
                nearest_fault = fault

        nearest_plate = None
        nearest_plate_dist = float("inf")
        for plate in plates:
            dist = haversine_km(event.latitude, event.longitude, plate["lat"], plate["lon"])
            if dist < nearest_plate_dist:
                nearest_plate_dist = dist
                nearest_plate = plate

        update: dict[str, Any] = {}
        if nearest_fault:
            update.update({
                "nearest_fault_name": nearest_fault.get("name"),
                "distance_to_nearest_fault_km": round(nearest_fault_dist, 2),
                "fault_system": nearest_fault.get("fault_system"),
                "fault_type": nearest_fault.get("fault_type"),
                "tectonic_zone": nearest_fault.get("tectonic_zone"),
            })
        if nearest_plate:
            update.update({
                "nearest_plate_boundary": nearest_plate.get("name"),
                "distance_to_plate_boundary_km": round(nearest_plate_dist, 2),
                "plate_context": nearest_plate.get("plate_context"),
            })
        enriched.append(event.model_copy(update=update))
    return enriched
