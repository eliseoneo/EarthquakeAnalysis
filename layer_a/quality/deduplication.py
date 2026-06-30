"""Deduplicación de eventos entre catálogos."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from layer_a.geo.distance import haversine_km
from layer_a.models import SeismicEvent


def _events_match(a: SeismicEvent, b: SeismicEvent, cfg: dict[str, Any]) -> bool:
    time_delta = abs((a.datetime_utc - b.datetime_utc).total_seconds())
    if time_delta > cfg["time_tolerance_seconds"]:
        return False
    dist = haversine_km(a.latitude, a.longitude, b.latitude, b.longitude)
    if dist > cfg["distance_tolerance_km"]:
        return False
    if abs(a.magnitude - b.magnitude) > cfg["magnitude_tolerance"]:
        return False
    if abs(a.depth_km - b.depth_km) > cfg["depth_tolerance_km"]:
        return False
    return True


def _conflict_fields(a: SeismicEvent, b: SeismicEvent) -> list[str]:
    fields: list[str] = []
    if abs(a.magnitude - b.magnitude) > 0.1:
        fields.append("magnitude")
    if abs(a.depth_km - b.depth_km) > 5:
        fields.append("depth_km")
    if haversine_km(a.latitude, a.longitude, b.latitude, b.longitude) > 5:
        fields.append("location")
    return fields


def _pick_preferred(events: list[SeismicEvent], priority: list[str]) -> SeismicEvent:
    for source in priority:
        for event in events:
            if event.source == source:
                return deepcopy(event)
    return deepcopy(events[0])


def deduplicate_events(
    events: list[SeismicEvent],
    cfg: dict[str, Any],
    source_priority: list[str],
) -> list[SeismicEvent]:
    clusters: list[list[SeismicEvent]] = []
    assigned: set[str] = set()

    for event in sorted(events, key=lambda e: e.datetime_utc):
        if event.event_id in assigned:
            continue
        cluster = [event]
        assigned.add(event.event_id)
        for other in events:
            if other.event_id in assigned:
                continue
            if _events_match(event, other, cfg):
                cluster.append(other)
                assigned.add(other.event_id)
        clusters.append(cluster)

    canonical: list[SeismicEvent] = []
    for cluster in clusters:
        if len(cluster) == 1:
            canonical.append(cluster[0])
            continue
        merged = _pick_preferred(cluster, source_priority)
        merged_ids = [e.event_id for e in cluster]
        conflicts: list[str] = []
        for i, a in enumerate(cluster):
            for b in cluster[i + 1 :]:
                conflicts.extend(_conflict_fields(a, b))
        merged.merged_source_ids = merged_ids
        merged.source_count = len(cluster)
        merged.has_conflict = bool(conflicts)
        merged.conflict_fields = sorted(set(conflicts))
        merged.event_id = f"canonical_{merged.event_id}"
        canonical.append(merged)
    return canonical
