#!/usr/bin/env python3
"""Flujo UI: Proyección Venezuela 2026 (inicial → similitud → efectividad → calibrado)."""

from __future__ import annotations

from datetime import date
from typing import Any

from projection_model import (
    TARGET_CASE_ID,
    CalibrationResult,
    ForwardProjectionRow,
    build_calibrated_forward_projection_row,
    build_forward_projection_row,
    build_hindcast_certainty_rows,
    calibrate_from_hindcast,
)


def _projection_row_table(row: ForwardProjectionRow | None) -> list[list[Any]]:
    if row is None:
        return []
    return [[
        row.case_id,
        row.scenario,
        row.as_of_date,
        row.elapsed_days_from_main,
        row.forward_days,
        row.magnitude_target_mw,
        row.omori_K,
        row.b_value,
        row.additional_expected_aftershocks,
        row.expected_max_magnitude_mw,
        row.probability_m_ge_target,
        row.observed_max_magnitude_mw,
    ]]


PROJECTION_TABLE_HEADERS = [
    "case_id", "scenario", "as_of_date", "elapsed_days", "forward_days",
    "magnitude_target_mw", "omori_K", "b_value", "expected_aftershocks",
    "expected_max_mw", "probability_m_ge_target", "observed_max_mw",
]


def _plot_single_projection(
    row: ForwardProjectionRow | None,
    title: str,
):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 4))
    if row is None:
        ax.text(0.5, 0.5, "Sin datos de proyección", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        return fig

    labels = ["P(M≥objetivo)", "Mmax esperada", "K Omori", "b-value"]
    values = [
        row.probability_m_ge_target * 100,
        row.expected_max_magnitude_mw,
        row.omori_K,
        row.b_value,
    ]
    colors = ["#E63946", "#457B9D", "#2A9D8F", "#F4A261"]
    ax.bar(labels, values, color=colors)
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=15)
    fig.tight_layout()
    return fig


def _plot_similarity_cases(
    case_ids: list[str],
    case_lookup: dict[str, dict[str, Any]],
    horizon_days: int,
    reference_case_id: str,
    similarity_stats_fn,
):
    import matplotlib.pyplot as plt

    stats = similarity_stats_fn(case_ids, horizon_days, case_lookup)
    ref_prob = next((p for cid, _, _, p in stats if cid == reference_case_id), None)

    labels = [cid for cid, _, _, _ in stats if cid != reference_case_id]
    probs = [p for cid, _, _, p in stats if cid != reference_case_id]

    fig, ax = plt.subplots(figsize=(10, 4.8))
    if not probs:
        ax.text(0.5, 0.5, "Sin datos de similitud", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        return fig

    ax.bar(labels, probs, color="#8D99AE")
    if ref_prob is not None:
        ax.axhline(
            ref_prob,
            linestyle="--",
            color="#E63946",
            label=f"Referencia {reference_case_id}: {ref_prob:.1f}%",
        )
        ax.legend()
    ax.set_title(f"Similitud de magnitud (horizonte {horizon_days}d) vs {reference_case_id}")
    ax.set_ylabel("% eventos similares")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    return fig


def _similarity_table_excluding_target(
    case_ids: list[str],
    case_lookup: dict[str, dict[str, Any]],
    horizon_days: int,
    reference_case_id: str,
    similarity_stats_fn,
    similarity_table_fn,
) -> list[list[Any]]:
    others = [cid for cid in case_ids if cid != reference_case_id]
    rows = similarity_table_fn(others, horizon_days, case_lookup)
    ref_rows = similarity_table_fn([reference_case_id], horizon_days, case_lookup)
    if ref_rows:
        ref = ref_rows[0]
        ref[0] = f"{ref[0]} (referencia)"
        rows.insert(0, ref)
    return rows


def _plot_hindcast_training(
    case_ids: list[str],
    case_lookup: dict[str, dict[str, Any]],
    validation_days: int,
    magnitude_target: float,
    hindcast_rows_fn,
):
    import matplotlib.pyplot as plt

    rows = hindcast_rows_fn(
        case_ids,
        case_lookup,
        validation_days,
        magnitude_target,
        "base",
        exclude_case_ids=(TARGET_CASE_ID,),
    )
    fig, ax = plt.subplots(figsize=(10, 4.8))
    if not rows:
        ax.text(0.5, 0.5, "Sin datos hindcast", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        return fig

    labels = [r.case_id for r in rows]
    certainties = [r.certainty_percent for r in rows]
    ax.bar(labels, certainties, color="#4CC9F0")
    ax.set_ylim(0, 100)
    ax.set_title(
        f"Efectividad del modelo en eventos históricos "
        f"(M≥{magnitude_target:.1f}, {validation_days}d posteriores)"
    )
    ax.set_ylabel("Certeza (%)")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    return fig


def _hindcast_training_table(
    case_ids: list[str],
    case_lookup: dict[str, dict[str, Any]],
    validation_days: int,
    magnitude_target: float,
    hindcast_table_fn,
) -> list[list[Any]]:
    return hindcast_table_fn(
        case_ids,
        case_lookup,
        validation_days,
        magnitude_target,
        "base",
        exclude_case_ids=(TARGET_CASE_ID,),
    )


def _calibration_markdown(calibration: CalibrationResult | None) -> str:
    if calibration is None:
        return "No se pudo calibrar con los eventos históricos disponibles."
    cases = ", ".join(calibration.training_case_ids)
    return (
        f"**Calibración a partir de eventos anteriores** ({cases})\n\n"
        f"- `k_factor`: {calibration.k_factor}\n"
        f"- `b_offset`: {calibration.b_offset}\n"
        f"- `k_obs_below_target_factor`: {calibration.k_obs_below_target_factor}\n"
        f"- Brier medio entrenamiento: {calibration.mean_brier_score}\n"
        f"- Certeza media entrenamiento: {calibration.mean_certainty_percent}%"
    )


def render_venezuela_workflow(
    case_ids: list[str],
    case_lookup: dict[str, dict[str, Any]],
    as_of_date: date,
    forward_days: int,
    validation_days: int,
    magnitude_target: float,
    horizon_days: int,
    similarity_stats_fn,
    similarity_table_fn,
    hindcast_table_fn,
) -> tuple[Any, ...]:
    target_case = case_lookup.get(TARGET_CASE_ID)
    initial_row = None
    calibrated_row = None
    calibration: CalibrationResult | None = None

    if target_case:
        seismic = target_case.get("advanced_features", {}).get("seismic", {})
        similarity = target_case.get("similar_magnitude_probability_dates", {})
        if isinstance(seismic, dict) and isinstance(similarity, dict):
            initial_row = build_forward_projection_row(
                TARGET_CASE_ID,
                seismic,
                similarity,
                as_of_date,
                forward_days,
                magnitude_target,
                scenario_key="base",
            )

    calibration = calibrate_from_hindcast(
        case_ids,
        case_lookup,
        validation_days,
        magnitude_target,
    )
    if calibration is not None:
        calibrated_row = build_calibrated_forward_projection_row(
            case_lookup,
            calibration,
            as_of_date,
            forward_days,
            magnitude_target,
        )

    initial_plot = _plot_single_projection(
        initial_row,
        f"1. Proyección inicial — {TARGET_CASE_ID} (escenario base)",
    )
    initial_table = _projection_row_table(initial_row)

    similarity_plot = _plot_similarity_cases(
        case_ids,
        case_lookup,
        horizon_days,
        TARGET_CASE_ID,
        similarity_stats_fn,
    )
    similarity_table = _similarity_table_excluding_target(
        case_ids,
        case_lookup,
        horizon_days,
        TARGET_CASE_ID,
        similarity_stats_fn,
        similarity_table_fn,
    )

    effectiveness_plot = _plot_hindcast_training(
        case_ids,
        case_lookup,
        validation_days,
        magnitude_target,
        build_hindcast_certainty_rows,
    )
    effectiveness_table = _hindcast_training_table(
        case_ids,
        case_lookup,
        validation_days,
        magnitude_target,
        hindcast_table_fn,
    )

    calibration_md = _calibration_markdown(calibration)
    calibrated_plot = _plot_single_projection(
        calibrated_row,
        f"4. Proyección calibrada — {TARGET_CASE_ID} (ajuste por eventos históricos)",
    )
    calibrated_table = _projection_row_table(calibrated_row)

    return (
        initial_plot,
        initial_table,
        similarity_plot,
        similarity_table,
        effectiveness_plot,
        effectiveness_table,
        calibration_md,
        calibrated_plot,
        calibrated_table,
    )


def mount_venezuela_projection_panel(
    gr_module: Any,
    case_ids: list[str],
    case_lookup: dict[str, dict[str, Any]],
    default_as_of: str,
    default_forward_days: int,
    default_validation_days: int,
    default_magnitude: float,
    default_horizon: int,
    similarity_stats_fn,
    similarity_table_fn,
    hindcast_table_fn,
    parse_as_of_date_fn,
) -> None:
    gr = gr_module

    gr.Markdown(
        "## Proyección Venezuela 2026\n"
        "Flujo: **proyección inicial** → **similitudes históricas** → "
        "**efectividad del modelo** → **proyección calibrada**."
    )
    with gr.Row():
        wf_as_of = gr.Textbox(value=default_as_of, label="Fecha de corte (YYYY-MM-DD)")
        wf_forward_days = gr.Slider(1, 120, value=default_forward_days, step=1, label="Días forward")
        wf_validation_days = gr.Slider(1, 120, value=default_validation_days, step=1, label="Días validación hindcast")
        wf_magnitude = gr.Number(value=default_magnitude, label="Magnitud objetivo (Mw)", minimum=4.0, maximum=9.5)
        wf_horizon = gr.Slider(1, 365, value=default_horizon, step=1, label="Horizonte similitud (días)")

    update_wf = gr.Button("Actualizar flujo de proyección", variant="primary")

    gr.Markdown("### 1. Proyección inicial (`venezuela_2026`, escenario base)")
    with gr.Row():
        wf_initial_plot = gr.Plot(label="Proyección inicial")
        wf_initial_table = gr.Dataframe(headers=PROJECTION_TABLE_HEADERS, label="Detalle proyección inicial")

    gr.Markdown("### 2. Similitudes con otros eventos históricos")
    with gr.Row():
        wf_similarity_plot = gr.Plot(label="Comparativa de similitud")
        wf_similarity_table = gr.Dataframe(
            headers=["case_id", "n_eventos_horizonte", "n_similares", "%"],
            label="Tabla de similitud",
        )

    gr.Markdown("### 3. Efectividad del modelo (eventos anteriores, días subsiguientes observados)")
    with gr.Row():
        wf_effectiveness_plot = gr.Plot(label="Certeza hindcast eventos históricos")
        wf_effectiveness_table = gr.Dataframe(
            headers=[
                "case_id", "model_name", "scenario", "validation_days",
                "magnitude_target_mw", "predicted_probability_m_ge_target",
                "observed_event_reached", "observed_max_magnitude_mw",
                "brier_score", "certainty_percent",
                "certainty_delta_vs_venezuela_2026", "certainty_vs_venezuela_2026_percent",
            ],
            label="Detalle efectividad",
        )

    gr.Markdown("### 4. Proyección calibrada (`venezuela_2026`, ajuste por eventos históricos)")
    wf_calibration_md = gr.Markdown()
    with gr.Row():
        wf_calibrated_plot = gr.Plot(label="Proyección calibrada")
        wf_calibrated_table = gr.Dataframe(headers=PROJECTION_TABLE_HEADERS, label="Detalle proyección calibrada")

    def _run_workflow(as_of_s, fwd, val_d, mag, horizon):
        try:
            as_of = parse_as_of_date_fn(as_of_s)
        except ValueError:
            as_of = date.today()
        return render_venezuela_workflow(
            case_ids,
            case_lookup,
            as_of,
            int(fwd),
            int(val_d),
            float(mag),
            int(horizon),
            similarity_stats_fn,
            similarity_table_fn,
            hindcast_table_fn,
        )

    update_wf.click(
        fn=_run_workflow,
        inputs=[wf_as_of, wf_forward_days, wf_validation_days, wf_magnitude, wf_horizon],
        outputs=[
            wf_initial_plot, wf_initial_table,
            wf_similarity_plot, wf_similarity_table,
            wf_effectiveness_plot, wf_effectiveness_table,
            wf_calibration_md,
            wf_calibrated_plot, wf_calibrated_table,
        ],
    )

    demo_load_inputs = [wf_as_of, wf_forward_days, wf_validation_days, wf_magnitude, wf_horizon]
    demo_load_outputs = [
        wf_initial_plot, wf_initial_table,
        wf_similarity_plot, wf_similarity_table,
        wf_effectiveness_plot, wf_effectiveness_table,
        wf_calibration_md,
        wf_calibrated_plot, wf_calibrated_table,
    ]
    return demo_load_inputs, demo_load_outputs, _run_workflow
