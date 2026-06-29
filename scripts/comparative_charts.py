#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from validation import ROOT, discover_files, load_yaml

CASE_LIBRARY_PATTERN = "case_library/**/event.yaml"

METRICS: dict[str, tuple[str, ...]] = {
    "Magnitud Mw": ("magnitude_mw",),
    "Profundidad (km)": ("depth_km",),
    "Distancia a ciudades (km)": ("distance_to_cities_km",),
    "Replicas (conteo)": ("advanced_features", "seismic", "aftershock_count"),
    "Omori p-value": ("advanced_features", "seismic", "omori_decay_p"),
    "b-value Gutenberg-Richter": ("advanced_features", "seismic", "gutenberg_richter_b_value"),
    "Slip rate (mm/anio)": ("advanced_features", "seismic", "estimated_slip_rate_mm_per_year"),
    "Vs30 (m/s)": ("advanced_features", "geological_geotechnical", "vs30_m_per_s"),
    "Lluvia 30d (mm)": ("advanced_features", "climatic", "rainfall_30d_mm"),
    "Poblacion expuesta": ("advanced_features", "human_urban", "exposed_population"),
}


def _read_path(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    cursor: Any = data
    for key in keys:
        if not isinstance(cursor, dict) or key not in cursor:
            return None
        cursor = cursor[key]
    return cursor


def _load_case_library() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in discover_files([CASE_LIBRARY_PATTERN], ROOT):
        doc = load_yaml(path)
        doc["_path"] = str(path.relative_to(ROOT))
        cases.append(doc)
    return cases


def _build_case_lookup(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for case in cases:
        case_id = str(case.get("case_id", case.get("_path", "unknown_case")))
        lookup[case_id] = case
    return lookup


def _series_for_metric(
    case_ids: list[str], metric_label: str, case_lookup: dict[str, dict[str, Any]]
) -> tuple[list[str], list[float]]:
    path = METRICS[metric_label]
    labels: list[str] = []
    values: list[float] = []
    for case_id in case_ids:
        case = case_lookup.get(case_id)
        if not case:
            continue
        value = _read_path(case, path)
        if isinstance(value, (int, float)):
            labels.append(case_id)
            values.append(float(value))
    return labels, values


def _plot_bar(case_ids: list[str], metric_label: str, case_lookup: dict[str, dict[str, Any]]):
    import matplotlib.pyplot as plt

    labels, values = _series_for_metric(case_ids, metric_label, case_lookup)
    fig, ax = plt.subplots(figsize=(10, 4.8))
    if not values:
        ax.text(0.5, 0.5, "No numeric values found", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        return fig

    ax.bar(labels, values, color="#2E86AB")
    ax.set_title(f"Comparativa: {metric_label}")
    ax.set_ylabel(metric_label)
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    return fig


def _plot_scatter(
    case_ids: list[str], x_metric: str, y_metric: str, case_lookup: dict[str, dict[str, Any]]
):
    import matplotlib.pyplot as plt

    x_path = METRICS[x_metric]
    y_path = METRICS[y_metric]

    x_values: list[float] = []
    y_values: list[float] = []
    labels: list[str] = []

    for case_id in case_ids:
        case = case_lookup.get(case_id)
        if not case:
            continue
        x = _read_path(case, x_path)
        y = _read_path(case, y_path)
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            x_values.append(float(x))
            y_values.append(float(y))
            labels.append(case_id)

    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    if not x_values:
        ax.text(0.5, 0.5, "No comparable numeric pairs", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        return fig

    ax.scatter(x_values, y_values, color="#F18F01")
    for i, label in enumerate(labels):
        ax.annotate(label, (x_values[i], y_values[i]), fontsize=8, xytext=(4, 4), textcoords="offset points")
    ax.set_title(f"Dispersion: {x_metric} vs {y_metric}")
    ax.set_xlabel(x_metric)
    ax.set_ylabel(y_metric)
    fig.tight_layout()
    return fig


def _plot_similarity_probability(
    case_ids: list[str],
    horizon_days: int,
    case_lookup: dict[str, dict[str, Any]],
):
    import matplotlib.pyplot as plt

    stats_rows = _similarity_stats(case_ids, horizon_days, case_lookup)
    labels = [row[0] for row in stats_rows]
    probabilities = [row[3] for row in stats_rows]

    fig, ax = plt.subplots(figsize=(10, 4.8))
    if not probabilities:
        ax.text(0.5, 0.5, "No hay eventos suficientes para el horizonte seleccionado", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        return fig

    ax.bar(labels, probabilities, color="#6A4C93")
    ax.set_ylim(0, 100)
    ax.set_title(f"Probabilidad de magnitud similar (<= {horizon_days} dias)")
    ax.set_ylabel("Probabilidad (%)")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    return fig


def _similarity_stats(
    case_ids: list[str], horizon_days: int, case_lookup: dict[str, dict[str, Any]]
) -> list[tuple[str, int, int, float]]:
    rows: list[tuple[str, int, int, float]] = []
    for case_id in case_ids:
        case = case_lookup.get(case_id)
        if not case:
            continue

        similarity_block = case.get("similar_magnitude_probability_dates", {})
        events = similarity_block.get("highest_magnitude_events", [])
        reference_mw = similarity_block.get("reference_magnitude_mw")
        delta = similarity_block.get("magnitude_similarity_delta_mw")

        if not isinstance(reference_mw, (int, float)) or not isinstance(delta, (int, float)):
            continue
        if not isinstance(events, list):
            continue

        horizon_events = [
            event
            for event in events
            if isinstance(event, dict)
            and isinstance(event.get("days_after_main"), int)
            and event["days_after_main"] <= horizon_days
            and isinstance(event.get("magnitude_mw"), (int, float))
        ]

        if not horizon_events:
            continue

        n_events = len(horizon_events)
        n_similar = sum(
            1
            for event in horizon_events
            if abs(float(event["magnitude_mw"]) - float(reference_mw)) <= float(delta)
        )
        probability = (n_similar / n_events) * 100.0
        rows.append((case_id, n_events, n_similar, probability))

    rows.sort(key=lambda row: row[3], reverse=True)
    return rows


def _similarity_summary_table(
    case_ids: list[str], horizon_days: int, case_lookup: dict[str, dict[str, Any]]
) -> list[list[str | int | float]]:
    rows = _similarity_stats(case_ids, horizon_days, case_lookup)
    return [[case_id, n_events, n_similar, round(probability, 2)] for case_id, n_events, n_similar, probability in rows]


def build_interface():
    import gradio as gr

    cases = _load_case_library()
    case_lookup = _build_case_lookup(cases)
    case_ids = sorted(case_lookup.keys())
    metric_labels = list(METRICS.keys())

    default_cases = case_ids[: min(5, len(case_ids))]
    default_metric = "Magnitud Mw"
    default_x = "Magnitud Mw"
    default_y = "Replicas (conteo)"

    with gr.Blocks(title="EarthquakeAnalysis - Comparative Charts") as demo:
        gr.Markdown("## Graficas comparativas de `case_library/`")
        gr.Markdown(
            "Selecciona casos y metricas para comparar magnitudes, profundidad y variables de Fase 3."
        )

        selected_cases = gr.Dropdown(
            choices=case_ids,
            value=default_cases,
            multiselect=True,
            label="Casos comparativos",
        )

        with gr.Row():
            bar_metric = gr.Dropdown(
                choices=metric_labels, value=default_metric, label="Metrica para barras"
            )
            x_metric = gr.Dropdown(
                choices=metric_labels, value=default_x, label="Eje X (dispersion)"
            )
            y_metric = gr.Dropdown(
                choices=metric_labels, value=default_y, label="Eje Y (dispersion)"
            )
            horizon_days = gr.Slider(
                minimum=1,
                maximum=365,
                value=30,
                step=1,
                label="Horizonte post-evento (dias) para probabilidad similar",
            )

        update_button = gr.Button("Actualizar graficas", variant="primary")
        bar_plot = gr.Plot(label="Grafica de barras")
        scatter_plot = gr.Plot(label="Grafica de dispersion")
        with gr.Row():
            probability_plot = gr.Plot(
                label="Probabilidad comparativa de magnitud similar (highest_magnitude_events)"
            )
            probability_table = gr.Dataframe(
                headers=["case_id", "n_eventos_horizonte", "n_similares", "%"],
                datatype=["str", "number", "number", "number"],
                label="Resumen de probabilidad por caso",
                interactive=False,
            )

        def _render(
            case_values: list[str], bar_value: str, x_value: str, y_value: str, horizon_value: int
        ):
            use_cases = case_values or case_ids
            return (
                _plot_bar(use_cases, bar_value, case_lookup),
                _plot_scatter(use_cases, x_value, y_value, case_lookup),
                _plot_similarity_probability(use_cases, int(horizon_value), case_lookup),
                _similarity_summary_table(use_cases, int(horizon_value), case_lookup),
            )

        update_button.click(
            _render,
            inputs=[selected_cases, bar_metric, x_metric, y_metric, horizon_days],
            outputs=[bar_plot, scatter_plot, probability_plot, probability_table],
        )

        demo.load(
            _render,
            inputs=[selected_cases, bar_metric, x_metric, y_metric, horizon_days],
            outputs=[bar_plot, scatter_plot, probability_plot, probability_table],
        )

    return demo


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dashboard de graficas comparativas para case_library."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host de servicio")
    parser.add_argument("--port", type=int, default=7860, help="Puerto de servicio")
    parser.add_argument(
        "--share",
        action="store_true",
        help="Habilita enlace publico de Gradio cuando aplica.",
    )
    parser.add_argument(
        "--use-uvicorn",
        action="store_true",
        help="Levanta Gradio montado en FastAPI con Uvicorn.",
    )
    args = parser.parse_args()

    demo = build_interface()
    if args.use_uvicorn:
        from fastapi import FastAPI
        import gradio as gr
        import uvicorn

        app = FastAPI(title="EarthquakeAnalysis Comparative Charts")
        app = gr.mount_gradio_app(app, demo, path="/")
        uvicorn.run(app, host=args.host, port=args.port)
        return 0

    demo.launch(server_name=args.host, server_port=args.port, share=args.share)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
