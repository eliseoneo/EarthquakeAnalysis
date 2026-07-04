"""Componentes Gradio — Capa C H04 analisis del evento."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from layer_c.paths import PROCESSED_DIR, REFERENCE_DOC, REPORTS_DIR
from layer_c.pipeline import run_pipeline

HYPOTHESIS_HEADERS = ["hypothesis_id", "label", "statement", "status", "focus"]
EVIDENCE_HEADERS = ["evidence_id", "evidence_type", "target", "priority", "source_candidates"]
QUESTION_HEADERS = ["question_id", "question", "analysis_axis"]
CATALOG_SOURCE_HEADERS = [
    "source_name", "availability_status", "data_mode", "connector_status",
    "raw_record_count", "fixture_record_count", "processed_record_count",
    "layer_a_run_available",
]
CATALOG_EVENT_HEADERS = [
    "event_id", "source", "datetime_utc", "magnitude", "depth_km",
    "place", "is_mainshock", "nearest_fault_name", "distance_to_nearest_fault_km",
]
COVERAGE_MATRIX_HEADERS = [
    "evidence_id", "evidence_type", "source_name", "availability_status",
    "data_mode", "record_count", "supports_h04", "next_action",
]
EXTERNAL_SOURCE_HEADERS = [
    "source_name", "category", "domain", "site", "api_or_access",
    "target_layer", "priority_level",
]
EXTERNAL_PRIORITY_HEADERS = ["priority_tier", "priority_rank", "source_name"]
ACCELEROGRAPHY_HEADERS = [
    "record_id", "station_id", "station_name", "source", "measurement_mode",
    "pga_g", "pgv_cm_per_s", "site_class", "quality_flag",
]
GEOTECHNICAL_HEADERS = [
    "site_id", "location_name", "soil_type", "lithology", "vs30_m_per_s",
    "sedimentary_basin", "liquefaction_likelihood", "landslide_susceptibility", "quality_flag",
]


def _read_json(path: Path) -> list[dict[str, Any]] | dict[str, Any]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _table(records: list[dict[str, Any]], columns: list[str]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for record in records[:200]:
        row = []
        for column in columns:
            value = record.get(column, "")
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            row.append(value)
        rows.append(row)
    return rows


def run_layer_c_ui() -> tuple[
    str,
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    str,
    str,
    str,
    str,
    str,
]:
    summary = run_pipeline()
    summary_text = json.dumps(summary, indent=2, ensure_ascii=False, default=str)

    hypotheses = _read_json(PROCESSED_DIR / "h04_hypotheses.json")
    evidence_lines = _read_json(PROCESSED_DIR / "h04_evidence_lines.json")
    questions = _read_json(PROCESSED_DIR / "h04_scientific_questions.json")
    catalog_sources = _read_json(PROCESSED_DIR / "h04_catalog_source_coverage.json")
    catalog_events = _read_json(PROCESSED_DIR / "h04_catalog_event_candidates.json")
    coverage_matrix = _read_json(PROCESSED_DIR / "h04_source_coverage_matrix.json")
    external_sources = _read_json(PROCESSED_DIR / "h04_external_source_registry.json")
    external_priorities = _read_json(PROCESSED_DIR / "h04_external_source_priorities.json")
    accelerography = _read_json(PROCESSED_DIR.parent / "normalized" / "accelerography_station_records.json")
    geotechnical = _read_json(PROCESSED_DIR.parent / "normalized" / "geotechnical_site_records.json")
    report_path = REPORTS_DIR / "reporte_h04_evento_venezuela_2026.md"
    report_text = report_path.read_text(encoding="utf-8") if report_path.exists() else "Reporte no generado."
    reference_text = REFERENCE_DOC.read_text(encoding="utf-8") if REFERENCE_DOC.exists() else "Documento no disponible."
    provenance_path = REPORTS_DIR / "h04_evidence_provenance.md"
    schema_reference_path = REPORTS_DIR / "h04_schema_reference.md"
    provenance_text = provenance_path.read_text(encoding="utf-8") if provenance_path.exists() else "Procedencia no generada."
    schema_reference_text = schema_reference_path.read_text(encoding="utf-8") if schema_reference_path.exists() else "Referencia de esquemas no generada."
    external_reference_path = REPORTS_DIR / "h04_external_sources.md"
    external_reference_text = external_reference_path.read_text(encoding="utf-8") if external_reference_path.exists() else "Catalogo externo no generado."

    return (
        summary_text,
        _table(hypotheses if isinstance(hypotheses, list) else [], HYPOTHESIS_HEADERS),
        _table(evidence_lines if isinstance(evidence_lines, list) else [], EVIDENCE_HEADERS),
        _table(questions if isinstance(questions, list) else [], QUESTION_HEADERS),
        _table(catalog_sources if isinstance(catalog_sources, list) else [], CATALOG_SOURCE_HEADERS),
        _table(catalog_events if isinstance(catalog_events, list) else [], CATALOG_EVENT_HEADERS),
        _table(coverage_matrix if isinstance(coverage_matrix, list) else [], COVERAGE_MATRIX_HEADERS),
        _table(external_sources if isinstance(external_sources, list) else [], EXTERNAL_SOURCE_HEADERS),
        _table(external_priorities if isinstance(external_priorities, list) else [], EXTERNAL_PRIORITY_HEADERS),
        _table(accelerography if isinstance(accelerography, list) else [], ACCELEROGRAPHY_HEADERS),
        _table(geotechnical if isinstance(geotechnical, list) else [], GEOTECHNICAL_HEADERS),
        report_text,
        reference_text,
        provenance_text,
        schema_reference_text,
        external_reference_text,
    )


def mount_layer_c_panel(gr_module: Any) -> None:
    gr = gr_module

    gr.Markdown(
        "### Capa C — Analisis H04 del evento Venezuela 2026\n"
        "Estructura dedicada al analisis del evento como fenomeno observado, sin usar un marco de proyeccion."
    )
    run_btn = gr.Button("Construir analisis H04", variant="primary")

    with gr.Tab("Resumen"):
        summary_out = gr.Code(label="pipeline_summary.json", language="json")
    with gr.Tab("Hipotesis"):
        hypotheses_out = gr.Dataframe(headers=HYPOTHESIS_HEADERS, label="h04_hypotheses")
    with gr.Tab("Evidencia"):
        evidence_out = gr.Dataframe(headers=EVIDENCE_HEADERS, label="h04_evidence_lines")
    with gr.Tab("Preguntas cientificas"):
        questions_out = gr.Dataframe(headers=QUESTION_HEADERS, label="h04_scientific_questions")
    with gr.Tab("Catalogos enlazados"):
        catalog_sources_out = gr.Dataframe(headers=CATALOG_SOURCE_HEADERS, label="h04_catalog_source_coverage")
    with gr.Tab("Eventos catalogo H04"):
        catalog_events_out = gr.Dataframe(headers=CATALOG_EVENT_HEADERS, label="h04_catalog_event_candidates")
    with gr.Tab("Matriz de cobertura"):
        coverage_matrix_out = gr.Dataframe(headers=COVERAGE_MATRIX_HEADERS, label="h04_source_coverage_matrix")
    with gr.Tab("Fuentes externas"):
        external_sources_out = gr.Dataframe(headers=EXTERNAL_SOURCE_HEADERS, label="h04_external_source_registry")
    with gr.Tab("Priorizacion externa"):
        external_priorities_out = gr.Dataframe(headers=EXTERNAL_PRIORITY_HEADERS, label="h04_external_source_priorities")
    with gr.Tab("Acelerografia"):
        accelerography_out = gr.Dataframe(headers=ACCELEROGRAPHY_HEADERS, label="accelerography_station_records")
    with gr.Tab("Geotecnia"):
        geotechnical_out = gr.Dataframe(headers=GEOTECHNICAL_HEADERS, label="geotechnical_site_records")
    with gr.Tab("Reporte"):
        report_out = gr.Markdown(label="Reporte H04")
    with gr.Tab("Procedencia"):
        provenance_out = gr.Markdown(label="Procedencia H04")
    with gr.Tab("Esquemas"):
        schema_reference_out = gr.Markdown(label="Esquemas H04")
    with gr.Tab("Referencia externa"):
        external_reference_out = gr.Markdown(label="Fuentes externas H04")
    with gr.Tab("Documento base"):
        reference_out = gr.Markdown(label="Documento H04")

    run_btn.click(
        fn=run_layer_c_ui,
        inputs=[],
        outputs=[
            summary_out,
            hypotheses_out,
            evidence_out,
            questions_out,
            catalog_sources_out,
            catalog_events_out,
            coverage_matrix_out,
            external_sources_out,
            external_priorities_out,
            accelerography_out,
            geotechnical_out,
            report_out,
            reference_out,
            provenance_out,
            schema_reference_out,
            external_reference_out,
        ],
    )