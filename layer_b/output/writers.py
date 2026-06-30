"""Escritores de salida — Capa B."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from layer_b.formatting import format_datetime_utc
from layer_b.models import EnvironmentalIndexRecord, FeatureRecord


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_parquet_records(path: Path, records: list[dict[str, Any]]) -> None:
    _ensure_dir(path)
    try:
        import pandas as pd
        pd.DataFrame(records).to_parquet(path, index=False)
    except ImportError:
        path.with_suffix(".json").write_text(
            json.dumps(records, indent=2, default=str),
            encoding="utf-8",
        )


def write_json_compact(path: Path, payload: dict[str, Any]) -> None:
    _ensure_dir(path)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def write_environmental_report(
    path: Path,
    region_code: str,
    ref,
    indexes: EnvironmentalIndexRecord,
    top_comparisons: list[dict[str, Any]],
    correlation_rows: list[dict[str, Any]],
) -> None:
    _ensure_dir(path)
    lines = [
        "# Reporte Geofísico-Ambiental — Capa B",
        "",
        "## Identificación",
        f"- **Región:** {region_code}",
        f"- **Fecha de referencia UTC:** {format_datetime_utc(ref)}",
        "",
        "## Índices ambientales (0-100)",
        f"- **sst_activity_index:** {indexes.sst_activity_index}",
        f"- **rainfall_stress_index:** {indexes.rainfall_stress_index}",
        f"- **soil_saturation_index:** {indexes.soil_saturation_index}",
        f"- **atmospheric_pressure_index:** {indexes.atmospheric_pressure_index}",
        f"- **oceanic_anomaly_index:** {indexes.oceanic_anomaly_index}",
        f"- **environmental_anomaly_index:** {indexes.environmental_anomaly_index}",
        "",
        "## Comparación internacional (top 5)",
    ]
    for row in top_comparisons[:5]:
        lines.append(
            f"- **{row['region_code']}** — similitud {row['similarity_score']} "
            f"(evidencia {row['evidence_level']})"
        )

    lines.extend(["", "## Correlaciones destacadas"])
    for row in correlation_rows[:8]:
        lines.append(
            f"- {row['variable_x']} vs {row['variable_y']} ({row['method']}): "
            f"r={row.get('coefficient')} p={row.get('p_value')} [{row['evidence_level']}]"
        )

    lines.extend([
        "",
        "## Incertidumbres",
        "- Análisis correlacional; no afirmar causalidad sísmica sin evidencia estadística robusta.",
        "- Variables astronómicas con peso exploratorio (evidencia C salvo validación cruzada).",
        "",
        "## Nivel de evidencia",
        f"- **Índices:** {indexes.evidence_level}",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
