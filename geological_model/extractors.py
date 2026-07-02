"""Extracción de features desde event_cases y case_library."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from geological_model.models import GeologicalInputFeatures


def _read_path(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def extract_from_event_document(
    data: dict[str, Any],
    source_document: str,
    insar_displacement_cm: float | None = None,
    insar_quality: str = "unknown",
) -> GeologicalInputFeatures:
    """Mapea advanced_features del esquema a entradas del FCN geológico."""
    event_id = str(data.get("event_id", "unknown"))
    seismic = _read_path(data, ("advanced_features", "seismic")) or {}
    geo = _read_path(data, ("advanced_features", "geological_geotechnical")) or {}
    climatic = _read_path(data, ("advanced_features", "climatic")) or {}

    nearby_faults = geo.get("nearby_geological_faults")
    if not isinstance(nearby_faults, list):
        nearby_faults = []

    return GeologicalInputFeatures(
        event_id=event_id,
        source_document=source_document,
        insar_displacement_cm=insar_displacement_cm,
        insar_quality=insar_quality,
        distance_to_fault_km=_as_float(seismic.get("distance_to_fault_km")),
        estimated_slip_rate_mm_per_year=_as_float(seismic.get("estimated_slip_rate_mm_per_year")),
        nearby_geological_faults=[str(f) for f in nearby_faults],
        fault_count=len(nearby_faults),
        vs30_m_per_s=_as_float(geo.get("vs30_m_per_s")),
        slope_degrees=_as_float(geo.get("slope_degrees")),
        soil_moisture_index=_as_float(climatic.get("soil_moisture_index")),
        liquefaction_likelihood=_as_str(geo.get("liquefaction_likelihood")),
        distance_to_coast_or_rivers_km=_as_float(geo.get("distance_to_coast_or_rivers_km")),
        landslide_susceptibility=_as_str(geo.get("landslide_susceptibility")),
        magnitude_mw=_as_float(seismic.get("magnitude_mw")),
        gutenberg_richter_b_value=_as_float(seismic.get("gutenberg_richter_b_value")),
    )


def discover_event_documents(root: Path, patterns: list[str] | None = None) -> list[Path]:
    """Descubre YAML/JSON de casos en event_cases y case_library."""
    globs = patterns or [
        "event_cases/**/event.yaml",
        "case_library/**/event.yaml",
        "tests/fixtures/synthetic/*minimal.json",
    ]
    files: list[Path] = []
    for pattern in globs:
        files.extend(sorted(root.glob(pattern)))
    return files


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _as_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
