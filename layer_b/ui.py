"""Componentes Gradio — Capa B."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from layer_b.paths import ANALYTICS_DIR, FEATURES_DIR, REPORTS_DIR
from layer_b.pipeline import run_pipeline

FEATURE_HEADERS = ["region_code", "feature_name", "feature_value", "window_days", "evidence_level"]
INDEX_HEADERS = [
    "region_code", "environmental_anomaly_index",
    "sst_activity_index", "rainfall_stress_index", "soil_saturation_index",
]
COMPARISON_HEADERS = ["region_code", "reference_region", "similarity_score", "evidence_level"]


def read_parquet_or_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        alt = path.with_suffix(".json")
        if alt.exists():
            path = alt
        else:
            return []
    if path.suffix == ".parquet":
        try:
            import pandas as pd
            return pd.read_parquet(path).to_dict(orient="records")
        except ImportError:
            alt = path.with_suffix(".json")
            if alt.exists():
                return json.loads(alt.read_text(encoding="utf-8"))
            return []
    return json.loads(path.read_text(encoding="utf-8"))


def _table(records: list[dict[str, Any]], columns: list[str]) -> list[list[Any]]:
    return [[rec.get(col, "") for col in columns] for rec in records[:200]]


def run_layer_b_ui(use_synthetic: bool) -> tuple[str, list[list[Any]], list[list[Any]], list[list[Any]], str]:
    summary = run_pipeline(use_synthetic=use_synthetic)
    summary_text = json.dumps(summary, indent=2, default=str)

    features = read_parquet_or_json(FEATURES_DIR / "environmental_features.parquet")
    feature_table = _table(features, FEATURE_HEADERS)

    indexes = read_parquet_or_json(ANALYTICS_DIR / "environmental_indexes.parquet")
    index_table = _table(indexes, INDEX_HEADERS)

    comparisons = read_parquet_or_json(ANALYTICS_DIR / "international_comparison.parquet")
    comparison_table = _table(comparisons, COMPARISON_HEADERS)

    report_path = REPORTS_DIR / "reporte_ambiental_venezuela.md"
    report_text = report_path.read_text(encoding="utf-8") if report_path.exists() else "Reporte no generado."

    return summary_text, feature_table, index_table, comparison_table, report_text


def mount_layer_b_panel(gr_module: Any) -> None:
    gr = gr_module

    gr.Markdown(
        "### Capa B — Geofísica Ambiental\n"
        "Datos aislados en `layer_b_geophysical/`. Análisis correlacional y exploratorio "
        "(no implica causalidad sísmica)."
    )
    use_synthetic = gr.Checkbox(value=True, label="Generar/usar series sintéticas si no hay raw/")
    run_btn = gr.Button("Ejecutar pipeline Capa B", variant="primary")

    with gr.Tab("Resumen"):
        summary_out = gr.Code(label="pipeline_summary.json", language="json")
    with gr.Tab("Features"):
        features_out = gr.Dataframe(headers=FEATURE_HEADERS, label="environmental_features")
    with gr.Tab("Índices"):
        indexes_out = gr.Dataframe(headers=INDEX_HEADERS, label="environmental_indexes")
    with gr.Tab("Comparación internacional"):
        comparison_out = gr.Dataframe(headers=COMPARISON_HEADERS, label="international_comparison")
    with gr.Tab("Reporte"):
        report_out = gr.Markdown(label="Reporte ambiental")

    run_btn.click(
        fn=run_layer_b_ui,
        inputs=[use_synthetic],
        outputs=[summary_out, features_out, indexes_out, comparison_out, report_out],
    )
