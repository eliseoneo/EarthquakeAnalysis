"""Componentes Gradio reutilizables — Capa A."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from layer_a.paths import PROCESSED_DIR, REPORTS_DIR
from layer_a.pipeline import run_pipeline

CATALOG_HEADERS = [
    "event_id", "source", "datetime_utc", "magnitude", "magnitude_class",
    "depth_km", "depth_class", "nearest_fault_name", "distance_to_nearest_fault_km",
]
DOUBLET_HEADERS = [
    "doublet_id", "event_id_1", "event_id_2", "classification",
    "time_delta_seconds", "distance_km", "confidence_level",
]


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


def _summary_table(records: list[dict[str, Any]], columns: list[str]) -> list[list[Any]]:
    return [[rec.get(col, "") for col in columns] for rec in records[:200]]


def run_layer_a_ui(
    use_fixtures: bool,
    download_usgs: bool,
) -> tuple[str, list[list[Any]], list[list[Any]], str]:
    summary = run_pipeline(use_fixtures=use_fixtures, download_usgs=download_usgs)
    summary_text = json.dumps(summary, indent=2, default=str)

    catalog = read_parquet_or_json(PROCESSED_DIR / "catalog_with_faults.parquet")
    catalog_table = _summary_table(catalog, CATALOG_HEADERS)

    doublets = read_parquet_or_json(PROCESSED_DIR / "doublet_candidates.parquet")
    doublet_table = _summary_table(doublets, DOUBLET_HEADERS)

    report_path = REPORTS_DIR / "reporte_evento_venezuela_2026_06_24.md"
    report_text = (
        report_path.read_text(encoding="utf-8")
        if report_path.exists()
        else "Reporte no generado."
    )
    return summary_text, catalog_table, doublet_table, report_text


def mount_layer_a_panel(gr_module: Any) -> None:
    """Monta la UI de Capa A dentro de un contexto Gradio existente."""
    gr = gr_module

    gr.Markdown(
        "### Capa A — Tectónica Principal\n"
        "Datos aislados en `layer_a_tectonic/` (no mezclados con `event_cases/` ni `case_library/`)."
    )
    with gr.Row():
        use_fixtures = gr.Checkbox(value=True, label="Usar fixtures sintéticos si no hay raw/")
        download_usgs = gr.Checkbox(value=False, label="Descargar catálogo USGS a data/raw/")
    run_btn = gr.Button("Ejecutar pipeline Capa A", variant="primary")

    with gr.Tab("Resumen"):
        summary_out = gr.Code(label="pipeline_summary.json", language="json")
    with gr.Tab("Catálogo con fallas"):
        catalog_out = gr.Dataframe(headers=CATALOG_HEADERS, label="catalog_with_faults")
    with gr.Tab("Dobletes"):
        doublet_out = gr.Dataframe(headers=DOUBLET_HEADERS, label="doublet_candidates")
    with gr.Tab("Reporte Venezuela 2026-06-24"):
        report_out = gr.Markdown(label="Reporte tectónico")

    run_btn.click(
        fn=run_layer_a_ui,
        inputs=[use_fixtures, download_usgs],
        outputs=[summary_out, catalog_out, doublet_out, report_out],
    )
