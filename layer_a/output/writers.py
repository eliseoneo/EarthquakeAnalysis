"""Escritores de salida — Parquet, GeoJSON, JSON, Markdown."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from layer_a.formatting import format_datetime_utc
from layer_a.models import AftershockSequence, DoubletCandidate, SeismicEvent, TectonicIndexRecord


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_parquet_records(path: Path, records: list[dict[str, Any]]) -> None:
    _ensure_dir(path)
    try:
        import pandas as pd
        pd.DataFrame(records).to_parquet(path, index=False)
    except ImportError:
        _ensure_dir(path.with_suffix(".json"))
        path.with_suffix(".json").write_text(
            json.dumps(records, indent=2, default=str),
            encoding="utf-8",
        )


def write_geojson_events(path: Path, events: list[SeismicEvent]) -> None:
    _ensure_dir(path)
    features = []
    for event in events:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [event.longitude, event.latitude],
            },
            "properties": {
                k: v for k, v in event.to_flat_dict().items()
                if k not in {"latitude", "longitude"}
            },
        })
    payload = {"type": "FeatureCollection", "features": features}
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def write_json_compact(path: Path, payload: dict[str, Any]) -> None:
    _ensure_dir(path)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def write_mainshock_report(
    path: Path,
    mainshock: SeismicEvent,
    sequence: AftershockSequence | None,
    doublets: list[DoubletCandidate],
    indexes: TectonicIndexRecord | None,
) -> None:
    _ensure_dir(path)
    lines = [
        "# Reporte Tectónico del Evento",
        "",
        "## Identificación",
        f"- **ID:** {mainshock.event_id}",
        f"- **Fuente:** {mainshock.source}",
        f"- **Fecha UTC:** {format_datetime_utc(mainshock.datetime_utc)}",
        "",
        "## Ubicación",
        f"- **Lat/Lon:** {mainshock.latitude}, {mainshock.longitude}",
        f"- **Lugar:** {mainshock.place or 'N/D'}",
        "",
        "## Magnitud y Profundidad",
        f"- **Magnitud:** {mainshock.magnitude} ({mainshock.magnitude_type})",
        f"- **Magnitud preferida:** {mainshock.magnitude_preferred}",
        f"- **Clase magnitud:** {mainshock.magnitude_class}",
        f"- **Profundidad:** {mainshock.depth_km} km",
        f"- **Clase profundidad:** {mainshock.depth_class}",
        "",
        "## Contexto de Falla y Placa",
        f"- **Falla más cercana:** {mainshock.nearest_fault_name or 'N/D'}",
        f"- **Distancia a falla:** {mainshock.distance_to_nearest_fault_km or 'N/D'} km",
        f"- **Límite de placa:** {mainshock.nearest_plate_boundary or 'N/D'}",
        f"- **Contexto de placa:** {mainshock.plate_context or 'N/D'}",
        "",
    ]

    if sequence:
        lines.extend([
            "## Secuencia Posterior / Réplicas",
            f"- **Réplicas 3d/7d/30d/90d/365d:** "
            f"{sequence.aftershock_count_3d}/"
            f"{sequence.aftershock_count_7d}/"
            f"{sequence.aftershock_count_30d}/"
            f"{sequence.aftershock_count_90d}/"
            f"{sequence.aftershock_count_365d}",
            f"- **Máx réplica:** {sequence.max_aftershock_magnitude or 'N/D'}",
            f"- **Dispersión espacial:** {sequence.spatial_dispersion_km or 'N/D'} km",
            "",
        ])

    lines.extend([
        "## Mecanismo Focal",
        f"- **Tipo:** {mainshock.focal_mechanism_type or 'unknown'}",
        f"- **Strike/Dip/Rake:** {mainshock.strike}/{mainshock.dip}/{mainshock.rake}",
        "",
        "## Candidatura a Doblete o Multiplete",
    ])
    if doublets:
        for d in doublets[:5]:
            lines.append(
                f"- {d.doublet_id}: {d.classification} "
                f"(Δt={d.time_delta_seconds:.0f}s, ΔM={d.magnitude_delta:.2f})"
            )
    else:
        lines.append("- Sin candidatos detectados en el catálogo analizado.")

    if indexes:
        lines.extend([
            "",
            "## Índices Tectónicos",
            f"- **Actividad tectónica:** {indexes.tectonic_activity_index}",
            f"- **Proximidad a falla:** {indexes.fault_proximity_index}",
            f"- **Tasa de réplicas:** {indexes.aftershock_rate_index}",
            f"- **Riesgo por profundidad:** {indexes.depth_risk_index}",
            f"- **Energía sísmica:** {indexes.magnitude_energy_index}",
        ])

    lines.extend([
        "",
        "## Incertidumbres",
        "- Este reporte no predice fecha exacta de terremotos.",
        "- Los valores conservan trazabilidad de fuente y deduplicación.",
        "",
        "## Nivel de Evidencia Científica",
        f"- **Nivel global:** {mainshock.confidence_level}",
        "- Réplicas: A | Dobletes: B hasta validar mecanismo focal",
    ])

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
