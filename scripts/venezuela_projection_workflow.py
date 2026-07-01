#!/usr/bin/env python3
"""Flujo UI: Proyección Venezuela 2026 (inicial → similitud → efectividad → calibrado)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from persistence_store import latest_verification_report
from projection_model import (
    MAGNITUDE_MIN_REFERENCE,
    OMORI_C_DAYS,
    TARGET_CASE_ID,
    CalibrationResult,
    ForwardProjectionRow,
    build_calibrated_forward_projection_row,
    build_forward_projection_row,
    build_hindcast_certainty_rows,
    calibrate_from_hindcast,
    cum_omori,
    probability_m_ge,
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

DAILY_VERIFICATION_HEADERS = [
    "ventana", "fecha", "umbral_mw", "probabilidad_estimada", "valor_real",
    "acierto", "brier", "error_abs", "ajuste_aplicado",
]


def _latest_daily_effectiveness_report() -> dict[str, Any] | None:
    return latest_verification_report()


def _daily_adjustment_factor(report: dict[str, Any] | None, magnitude_target: float) -> float:
    if not report:
        return 1.0
    metrics = report.get("effectiveness_metrics", {}).get("threshold_metrics", [])
    if not isinstance(metrics, list):
        return 1.0

    selected = None
    for item in metrics:
        if not isinstance(item, dict):
            continue
        threshold = item.get("threshold_mw")
        if isinstance(threshold, (int, float)) and abs(float(threshold) - magnitude_target) < 1e-6:
            selected = item
            break
    if selected is None:
        selected = min(
            (item for item in metrics if isinstance(item, dict)),
            key=lambda item: abs(float(item.get("threshold_mw", magnitude_target)) - magnitude_target),
            default=None,
        )
    if not isinstance(selected, dict):
        return 1.0

    predicted = selected.get("predicted_probability", 0.0)
    observed = 1.0 if selected.get("observed_event_reached") else 0.0
    if not isinstance(predicted, (int, float)):
        return 1.0
    error = observed - float(predicted)
    return round(min(max(1.0 + error, 0.15), 1.75), 4)


def _next_day_prediction_from_row(
    row: ForwardProjectionRow | None,
    adjustment_factor: float,
    omori_p: float,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    if row is None:
        return None

    current_elapsed = int(row.elapsed_days_from_main)
    next_day_elapsed = current_elapsed + 1
    base_n = max(
        0.0,
        cum_omori(float(next_day_elapsed), row.omori_K, omori_p, OMORI_C_DAYS)
        - cum_omori(float(current_elapsed), row.omori_K, omori_p, OMORI_C_DAYS),
    )
    adjusted_n = base_n * adjustment_factor
    base_probability = probability_m_ge(
        base_n,
        row.magnitude_target_mw,
        row.b_value,
        MAGNITUDE_MIN_REFERENCE,
    )
    adjusted_probability = probability_m_ge(
        adjusted_n,
        row.magnitude_target_mw,
        row.b_value,
        MAGNITUDE_MIN_REFERENCE,
    )
    next_date = date.fromisoformat(row.as_of_date) + timedelta(days=1)
    return (
        {
            "date": next_date.isoformat(),
            "expected_aftershocks": round(base_n, 4),
            "probability": round(base_probability, 6),
            "adjustment_factor": 1.0,
        },
        {
            "date": next_date.isoformat(),
            "expected_aftershocks": round(adjusted_n, 4),
            "probability": round(adjusted_probability, 6),
            "adjustment_factor": adjustment_factor,
        },
    )


def _daily_verification_table(
    report: dict[str, Any] | None,
    tomorrow_base: dict[str, Any] | None,
    tomorrow_adjusted: dict[str, Any] | None,
    magnitude_target: float,
) -> list[list[Any]]:
    rows: list[list[Any]] = []
    if report:
        verification_date = report.get("verification_date", "")
        metrics = report.get("effectiveness_metrics", {}).get("threshold_metrics", [])
        if isinstance(metrics, list):
            for item in metrics:
                if not isinstance(item, dict):
                    continue
                rows.append([
                    "Estimado ayer -> real hoy",
                    verification_date,
                    item.get("threshold_mw", ""),
                    item.get("predicted_probability", ""),
                    item.get("observed_binary", ""),
                    item.get("hit", ""),
                    item.get("brier_score", ""),
                    item.get("absolute_error", ""),
                    1.0,
                ])
    if tomorrow_base:
        rows.append([
            "Estimacion manana base",
            tomorrow_base.get("date", ""),
            magnitude_target,
            tomorrow_base.get("probability", ""),
            "pendiente",
            "pendiente",
            "pendiente",
            "pendiente",
            tomorrow_base.get("adjustment_factor", 1.0),
        ])
    if tomorrow_adjusted:
        rows.append([
            "Estimacion manana ajustada",
            tomorrow_adjusted.get("date", ""),
            magnitude_target,
            tomorrow_adjusted.get("probability", ""),
            "pendiente",
            "pendiente",
            "pendiente",
            "pendiente",
            tomorrow_adjusted.get("adjustment_factor", ""),
        ])
    return rows


def _plot_daily_verification(
    report: dict[str, Any] | None,
    tomorrow_base: dict[str, Any] | None,
    tomorrow_adjusted: dict[str, Any] | None,
    magnitude_target: float,
):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 4.5))
    labels: list[str] = []
    values: list[float] = []
    colors: list[str] = []

    if report:
        metrics = report.get("effectiveness_metrics", {}).get("threshold_metrics", [])
        selected = None
        if isinstance(metrics, list):
            for item in metrics:
                if not isinstance(item, dict):
                    continue
                threshold = item.get("threshold_mw")
                if isinstance(threshold, (int, float)) and abs(float(threshold) - magnitude_target) < 1e-6:
                    selected = item
                    break
            if selected is None:
                selected = min(
                    (item for item in metrics if isinstance(item, dict)),
                    key=lambda item: abs(float(item.get("threshold_mw", magnitude_target)) - magnitude_target),
                    default=None,
                )
        if isinstance(selected, dict):
            labels.extend(["Ayer estimado", "Hoy real"])
            values.extend([
                float(selected.get("predicted_probability", 0.0)) * 100.0,
                100.0 if selected.get("observed_event_reached") else 0.0,
            ])
            colors.extend(["#457B9D", "#2A9D8F"])

    if tomorrow_base:
        labels.append("Manana base")
        values.append(float(tomorrow_base.get("probability", 0.0)) * 100.0)
        colors.append("#F4A261")
    if tomorrow_adjusted:
        labels.append("Manana ajustada")
        values.append(float(tomorrow_adjusted.get("probability", 0.0)) * 100.0)
        colors.append("#E63946")

    if not labels:
        ax.text(0.5, 0.5, "Sin verificacion diaria disponible", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        return fig

    ax.bar(labels, values, color=colors)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Probabilidad / ocurrencia real (%)")
    ax.set_title(f"Verificacion diaria y estimacion siguiente dia (M≥{magnitude_target:.1f})")
    ax.tick_params(axis="x", rotation=15)
    fig.tight_layout()
    return fig


def _daily_verification_markdown(
    report: dict[str, Any] | None,
    adjustment_factor: float,
    tomorrow_adjusted: dict[str, Any] | None,
) -> str:
    if report is None:
        return "No hay verificacion diaria disponible en `docs/venezuela_daily_effectiveness_*.json`."
    metrics = report.get("effectiveness_metrics", {})
    observed = report.get("observed_real_values_today", {})
    next_date = tomorrow_adjusted.get("date", "pendiente") if tomorrow_adjusted else "pendiente"
    next_prob = tomorrow_adjusted.get("probability", "pendiente") if tomorrow_adjusted else "pendiente"
    return (
        f"**Resumen diario**\n\n"
        f"- Fecha verificada: {report.get('verification_date', '')}\n"
        f"- Eventos reales hoy: {observed.get('events_count_all_magnitudes', 'N/D')} "
        f"(Mmax: {observed.get('max_magnitude_mw', 'N/D')})\n"
        f"- Brier medio: {metrics.get('mean_brier_score', 'N/D')} | "
        f"MAE: {metrics.get('mean_absolute_error', 'N/D')} | "
        f"Accuracy binaria: {metrics.get('binary_accuracy_at_0_5_threshold', 'N/D')}\n"
        f"- Factor de ajuste aplicado a manana: {adjustment_factor}\n"
        f"- Estimacion ajustada para {next_date}: {next_prob}"
    )


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
    target_omori_p = 1.0

    if target_case:
        seismic = target_case.get("advanced_features", {}).get("seismic", {})
        similarity = target_case.get("similar_magnitude_probability_dates", {})
        if isinstance(seismic, dict) and isinstance(similarity, dict):
            omori_p_value = seismic.get("omori_decay_p")
            if isinstance(omori_p_value, (int, float)):
                target_omori_p = float(omori_p_value)
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

    daily_report = _latest_daily_effectiveness_report()
    daily_adjustment = _daily_adjustment_factor(daily_report, magnitude_target)
    tomorrow_prediction = _next_day_prediction_from_row(
        calibrated_row or initial_row,
        daily_adjustment,
        target_omori_p,
    )
    tomorrow_base = tomorrow_prediction[0] if tomorrow_prediction else None
    tomorrow_adjusted = tomorrow_prediction[1] if tomorrow_prediction else None
    daily_plot = _plot_daily_verification(
        daily_report,
        tomorrow_base,
        tomorrow_adjusted,
        magnitude_target,
    )
    daily_table = _daily_verification_table(
        daily_report,
        tomorrow_base,
        tomorrow_adjusted,
        magnitude_target,
    )
    daily_md = _daily_verification_markdown(
        daily_report,
        daily_adjustment,
        tomorrow_adjusted,
    )

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
        daily_plot,
        daily_table,
        daily_md,
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
        "**efectividad del modelo** → **proyección calibrada** → "
        "**verificación diaria y estimación siguiente día**."
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

    gr.Markdown("### 5. Verificación diaria y estimación del siguiente día")
    wf_daily_md = gr.Markdown()
    with gr.Row():
        wf_daily_plot = gr.Plot(label="Ayer estimado, hoy real, mañana estimado")
        wf_daily_table = gr.Dataframe(
            headers=DAILY_VERIFICATION_HEADERS,
            label="Resumen diario y estimación siguiente día",
        )

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
            wf_daily_plot, wf_daily_table, wf_daily_md,
        ],
    )

    demo_load_inputs = [wf_as_of, wf_forward_days, wf_validation_days, wf_magnitude, wf_horizon]
    demo_load_outputs = [
        wf_initial_plot, wf_initial_table,
        wf_similarity_plot, wf_similarity_table,
        wf_effectiveness_plot, wf_effectiveness_table,
        wf_calibration_md,
        wf_calibrated_plot, wf_calibrated_table,
        wf_daily_plot, wf_daily_table, wf_daily_md,
    ]
    return demo_load_inputs, demo_load_outputs, _run_workflow
