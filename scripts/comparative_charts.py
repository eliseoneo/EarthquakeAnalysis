#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import sys
from datetime import date
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from projection_model import (
    PROJECTION_SCENARIOS,
    SCENARIO_CHOICES,
    build_forward_projection_rows,
    build_hindcast_certainty_rows,
    parse_date,
)
from validation import ROOT, discover_files, load_yaml

CASE_LIBRARY_PATTERN = "case_library/**/event.yaml"
PHASE5_MODELS_PATH = ROOT / "models/recommended_models_phase5.yaml"
INTERNATIONAL_CATALOG_VERIFICATION_PATH = (
    ROOT / "docs/venezuela_2026_international_catalog_verification.json"
)

METRICS: dict[str, tuple[str, ...]] = {
    "Magnitud Mw": ("magnitude_mw",),
    "Profundidad (km)": ("depth_km",),
    "Distancia a ciudades (km)": ("distance_to_cities_km",),
    "Replicas (conteo)": ("advanced_features", "seismic", "aftershock_count"),
    "Omori p-value": ("advanced_features", "seismic", "omori_decay_p"),
    "b-value Gutenberg-Richter": ("advanced_features", "seismic", "gutenberg_richter_b_value"),
    "Slip rate (mm/anio)": ("advanced_features", "seismic", "estimated_slip_rate_mm_per_year"),
    "PGA (g)": ("advanced_features", "seismic", "pga_g"),
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


def _load_phase5_models_catalog() -> dict[str, list[str]]:
    doc = load_yaml(PHASE5_MODELS_PATH)
    catalog: dict[str, list[str]] = {}
    for domain, models in doc.items():
        if not isinstance(domain, str):
            continue
        if not isinstance(models, list):
            continue
        cleaned = [str(model).strip() for model in models if isinstance(model, str) and model.strip()]
        catalog[domain] = cleaned
    return catalog


def _phase5_domain_choices(catalog: dict[str, list[str]]) -> list[tuple[str, str]]:
    return [("Todos los dominios", "todos")] + [(domain, domain) for domain in sorted(catalog)]


def _phase5_catalog_table(
    catalog: dict[str, list[str]],
    domain_filter: str,
) -> list[list[str | int]]:
    rows: list[list[str | int]] = []
    for domain in sorted(catalog):
        if domain_filter != "todos" and domain != domain_filter:
            continue
        for model_name in catalog[domain]:
            rows.append([domain, model_name, len(catalog[domain])])
    return rows


def _plot_phase5_domain_counts(
    catalog: dict[str, list[str]],
    domain_filter: str,
):
    import matplotlib.pyplot as plt

    domains = sorted(catalog.keys())
    if domain_filter != "todos":
        domains = [domain for domain in domains if domain == domain_filter]

    labels = domains
    values = [len(catalog[domain]) for domain in domains]

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    if not values:
        ax.text(0.5, 0.5, "No phase 5 model domains found", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        return fig

    ax.bar(labels, values, color="#6C757D")
    ax.set_title("Fase 5: modelos recomendados por dominio")
    ax.set_ylabel("Numero de modelos")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    return fig


def _linear_regression(x_values: list[float], y_values: list[float]) -> tuple[float, float, float]:
    n = len(x_values)
    if n < 2:
        return 0.0, 0.0, 0.0
    x_mean = sum(x_values) / n
    y_mean = sum(y_values) / n
    ss_xx = sum((x - x_mean) ** 2 for x in x_values)
    if ss_xx == 0:
        return 0.0, y_mean, 0.0
    ss_xy = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
    slope = ss_xy / ss_xx
    intercept = y_mean - slope * x_mean
    y_pred = [slope * x + intercept for x in x_values]
    ss_tot = sum((y - y_mean) ** 2 for y in y_values)
    ss_res = sum((y - yp) ** 2 for y, yp in zip(y_values, y_pred))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    return slope, intercept, r2


def _parse_as_of_date(value: str) -> date:
    try:
        return parse_date(str(value).strip())
    except ValueError as exc:
        raise ValueError("Fecha de corte invalida. Use formato YYYY-MM-DD.") from exc


def _projection_case_rows(
    case_ids: list[str],
    case_lookup: dict[str, dict[str, Any]],
    as_of_date: date,
    forward_days: int,
    max_magnitude_target: float,
    scenario_key: str,
) -> list:
    return build_forward_projection_rows(
        case_ids,
        case_lookup,
        as_of_date,
        forward_days,
        max_magnitude_target,
        scenario_key,
    )


def _plot_projection_probability(
    case_ids: list[str],
    case_lookup: dict[str, dict[str, Any]],
    as_of_date: date,
    forward_days: int,
    max_magnitude_target: float,
    scenario_key: str,
):
    import matplotlib.pyplot as plt

    rows = _projection_case_rows(
        case_ids,
        case_lookup,
        as_of_date,
        forward_days,
        max_magnitude_target,
        scenario_key,
    )
    labels = [row.case_id for row in rows]
    probs = [row.probability_m_ge_target * 100.0 for row in rows]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    if not probs:
        ax.text(0.5, 0.5, "No projection data found", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        return fig
    ax.bar(labels, probs, color="#8D99AE")
    ax.set_ylim(0, 100)
    scenario_label = next(
        (label for label, key in SCENARIO_CHOICES if key == scenario_key),
        scenario_key,
    )
    ax.set_title(
        "P(M >= "
        f"{max_magnitude_target:.2f}) forward {forward_days}d "
        f"desde {as_of_date.isoformat()} ({scenario_label})"
    )
    ax.set_ylabel("Probabilidad (%)")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    return fig


def _projection_table(
    case_ids: list[str],
    case_lookup: dict[str, dict[str, Any]],
    as_of_date: date,
    forward_days: int,
    max_magnitude_target: float,
    scenario_key: str,
) -> list[list[str | int | float | None]]:
    rows = _projection_case_rows(
        case_ids,
        case_lookup,
        as_of_date,
        forward_days,
        max_magnitude_target,
        scenario_key,
    )
    return [
        [
            row.case_id,
            row.scenario,
            row.as_of_date,
            row.elapsed_days_from_main,
            row.forward_days,
            row.horizon_days_from_main,
            row.magnitude_target_mw,
            row.omori_K,
            row.b_value,
            row.additional_expected_aftershocks,
            row.expected_max_magnitude_mw,
            row.expected_max_magnitude_capped_mw,
            row.probability_m_ge_target,
            row.observed_max_magnitude_mw,
            row.linear_regression_slope_prob_per_day,
            row.linear_regression_r2,
        ]
        for row in rows
    ]


def _hindcast_certainty_rows(
    case_ids: list[str],
    case_lookup: dict[str, dict[str, Any]],
    validation_days: int,
    max_magnitude_target: float,
    scenario_key: str,
    exclude_case_ids: tuple[str, ...] | None = None,
) -> list:
    return build_hindcast_certainty_rows(
        case_ids,
        case_lookup,
        validation_days,
        max_magnitude_target,
        scenario_key,
        exclude_case_ids=exclude_case_ids,
    )


def _plot_hindcast_certainty(
    case_ids: list[str],
    case_lookup: dict[str, dict[str, Any]],
    validation_days: int,
    max_magnitude_target: float,
    scenario_key: str,
):
    import matplotlib.pyplot as plt

    rows = _hindcast_certainty_rows(
        case_ids,
        case_lookup,
        validation_days,
        max_magnitude_target,
        scenario_key,
    )
    labels = [row.case_id for row in rows]
    certainties = [row.certainty_percent for row in rows]
    benchmark_certainty = next(
        (row.certainty_percent for row in rows if row.case_id == "venezuela_2026"),
        None,
    )
    if benchmark_certainty is None:
        benchmark_certainty = next(
            (
                round(row.certainty_percent - row.certainty_delta_vs_venezuela_2026, 2)
                for row in rows
                if row.certainty_delta_vs_venezuela_2026 is not None
            ),
            None,
        )
    fig, ax = plt.subplots(figsize=(10, 4.8))
    if not certainties:
        ax.text(0.5, 0.5, "No hindcast certainty data found", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        return fig

    ax.bar(labels, certainties, color="#4CC9F0")
    if benchmark_certainty is not None:
        ax.axhline(
            benchmark_certainty,
            linestyle="--",
            linewidth=1.2,
            color="#E63946",
            label=f"Referencia venezuela_2026: {benchmark_certainty:.2f}%",
        )
        ax.legend(loc="lower right")
    ax.set_ylim(0, 100)
    ax.set_title(
        "Certeza historica del modelo "
        f"(M >= {max_magnitude_target:.2f}, ventana {validation_days}d, escenario {scenario_key})"
    )
    ax.set_ylabel("Certeza (%)")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    return fig


def _plot_certainty_vs_venezuela_ranking(
    case_ids: list[str],
    case_lookup: dict[str, dict[str, Any]],
    validation_days: int,
    max_magnitude_target: float,
    scenario_key: str,
):
    import matplotlib.pyplot as plt

    rows = _hindcast_certainty_rows(
        case_ids,
        case_lookup,
        validation_days,
        max_magnitude_target,
        scenario_key,
    )
    ranked = sorted(
        [
            row
            for row in rows
            if row.certainty_vs_venezuela_2026_percent is not None
        ],
        key=lambda row: row.certainty_vs_venezuela_2026_percent or 0.0,
        reverse=True,
    )
    labels = [row.case_id for row in ranked]
    scores = [row.certainty_vs_venezuela_2026_percent or 0.0 for row in ranked]
    colors = ["#E63946" if cid == "venezuela_2026" else "#7209B7" for cid in labels]

    fig, ax = plt.subplots(figsize=(10, 4.8))
    if not scores:
        ax.text(
            0.5,
            0.5,
            "No hay indice certainty_vs_venezuela_2026 disponible",
            ha="center",
            va="center",
        )
        ax.axis("off")
        fig.tight_layout()
        return fig

    ax.bar(labels, scores, color=colors)
    ax.axhline(100.0, linestyle=":", linewidth=1.0, color="#6C757D", label="Referencia maxima (100%)")
    ax.set_ylim(0, 100)
    ax.set_title(
        "Ranking certainty_vs_venezuela_2026_percent "
        f"(M >= {max_magnitude_target:.2f}, ventana {validation_days}d)"
    )
    ax.set_ylabel("Cercania a certeza venezuela_2026 (%)")
    ax.tick_params(axis="x", rotation=45)
    ax.legend(loc="lower right")
    fig.tight_layout()
    return fig


def _hindcast_certainty_table(
    case_ids: list[str],
    case_lookup: dict[str, dict[str, Any]],
    validation_days: int,
    max_magnitude_target: float,
    scenario_key: str,
    exclude_case_ids: tuple[str, ...] | None = None,
) -> list[list[str | int | float | bool | None]]:
    rows = _hindcast_certainty_rows(
        case_ids,
        case_lookup,
        validation_days,
        max_magnitude_target,
        scenario_key,
        exclude_case_ids=exclude_case_ids,
    )
    return [
        [
            row.case_id,
            row.model_name,
            row.scenario,
            row.validation_days,
            row.magnitude_target_mw,
            row.predicted_probability_m_ge_target,
            row.observed_event_reached,
            row.observed_max_magnitude_mw,
            row.brier_score,
            row.certainty_percent,
            row.certainty_delta_vs_venezuela_2026,
            row.certainty_vs_venezuela_2026_percent,
        ]
        for row in rows
    ]


def _pga_summary_rows(
    case_ids: list[str], case_lookup: dict[str, dict[str, Any]]
) -> list[tuple[str, float, str, int, str]]:
    rows: list[tuple[str, float, str, int, str]] = []
    for case_id in case_ids:
        case = case_lookup.get(case_id)
        if not case:
            continue
        seismic = _read_path(case, ("advanced_features", "seismic"))
        if not isinstance(seismic, dict):
            continue
        pga = seismic.get("pga_g")
        if not isinstance(pga, (int, float)):
            continue
        mmi = seismic.get("mmi_intensity")
        estimates = seismic.get("pga_station_estimates")
        station_count = len(estimates) if isinstance(estimates, list) else 0
        quality = seismic.get("pga_measurement_quality")
        rows.append(
            (
                case_id,
                float(pga),
                str(mmi) if isinstance(mmi, str) else "",
                station_count,
                str(quality) if isinstance(quality, str) else "",
            )
        )
    rows.sort(key=lambda row: row[1], reverse=True)
    return rows


def _pga_has_estimated_indirect(case_ids: list[str], case_lookup: dict[str, dict[str, Any]]) -> bool:
    for case_id in case_ids:
        case = case_lookup.get(case_id)
        if not case:
            continue
        seismic = _read_path(case, ("advanced_features", "seismic"))
        if not isinstance(seismic, dict):
            continue
        if seismic.get("pga_measurement_quality") == "estimated_indirect":
            return True
    return False


def _pga_calibration_bias_notice(
    case_ids: list[str], case_lookup: dict[str, dict[str, Any]]
) -> str:
    warnings: list[str] = []
    for case_id in case_ids:
        case = case_lookup.get(case_id)
        if not case:
            continue
        seismic = _read_path(case, ("advanced_features", "seismic"))
        if not isinstance(seismic, dict):
            continue
        if seismic.get("pga_measurement_quality") != "estimated_indirect":
            continue
        custom = seismic.get("pga_calibration_bias_warning")
        if isinstance(custom, str) and custom.strip():
            warnings.append(f"**{case_id}:** {custom.strip()}")
        else:
            warnings.append(
                f"**{case_id}:** PGA indirecta/estimada; no usar para calibrar modelos "
                "forward sin correccion de sesgo."
            )

    if not warnings:
        return ""

    has_2026 = any(
        cid in {"venezuela_2026", "venezuela_2026_june"} for cid in case_ids
    )
    header = (
        "### Advertencia de sesgo PGA (estimaciones indirectas)\n\n"
        "**1967 no hubo acelerogramas fuertes** en Caracas; los valores NAS (Sozen et al. 1968) "
        "son **estimaciones post-evento**, no mediciones instrumentales. "
        "Comparar o calibrar con casos instrumentales (p. ej. 2026) puede **introducir sesgo** "
        "por metodo, sitio y epoca.\n\n"
    )
    body = "\n\n".join(f"- {line}" for line in warnings)
    if has_2026 and _pga_has_estimated_indirect(case_ids, case_lookup):
        body += (
            "\n\n> **Uso recomendado:** tratar PGA 1967 solo como contexto historico cualitativo; "
            "no como ancla numerica para proyecciones Omori/riesgo de `venezuela_2026`."
        )
    return header + body


def _load_international_catalog_verification() -> dict[str, Any] | None:
    if not INTERNATIONAL_CATALOG_VERIFICATION_PATH.exists():
        return None
    import json

    with INTERNATIONAL_CATALOG_VERIFICATION_PATH.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else None


def _international_catalog_notice(case_ids: list[str]) -> str:
    if not any(
        cid in {"venezuela_2026", "venezuela_2026_june"} for cid in case_ids
    ):
        return ""

    payload = _load_international_catalog_verification()
    if not payload:
        return (
            "### Catalogos internacionales (2026-06-24)\n\n"
            "No se encontro `docs/venezuela_2026_international_catalog_verification.json`."
        )

    lines = [
        "### Catalogos internacionales verificados (evento 2026-06-24)",
        "",
        f"Consulta al **{payload.get('as_of_date', 'N/A')}**.",
        "",
        "| Agencia | Pais | Estado | Eventos M>=4 |",
        "|---|---|---|---:|",
    ]
    for row in payload.get("catalog_results", []):
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {row.get('agency', '?')} | {row.get('country', '?')} | "
            f"{row.get('status', '?')} | {row.get('events_found_m_ge_4', 0)} |"
        )

    primary = payload.get("primary_events_usgs", [])
    if isinstance(primary, list) and primary:
        lines.extend(["", "**Eventos principales (USGS):**"])
        for event in primary:
            if not isinstance(event, dict):
                continue
            lines.append(
                f"- **{event.get('role', 'evento')}** "
                f"`{event.get('usgs_event_id', '?')}` "
                f"M{event.get('magnitude_mww', '?')} "
                f"({event.get('time_utc', '?')}); redes: {event.get('sources', '?')}."
            )

    aftershocks = payload.get("aftershocks_usgs_m_ge_4", [])
    if isinstance(aftershocks, list):
        lines.append(
            f"\n**Replicas USGS M>=4 adicionales:** {len(aftershocks)} "
            f"entre 2026-06-25 y {payload.get('as_of_date', '2026-06-29')}."
        )

    lines.append(
        "\n> GFZ/Geofon y EMSC no devolvieron eventos en la misma ventana/bbox al momento "
        "de la verificacion. Detalle completo en "
        "`docs/venezuela_2026_international_catalog_verification.json`."
    )
    return "\n".join(lines)


def _plot_pga_summary(case_ids: list[str], case_lookup: dict[str, dict[str, Any]]):
    import matplotlib.pyplot as plt

    rows = _pga_summary_rows(case_ids, case_lookup)
    labels = [row[0] for row in rows]
    values = [row[1] for row in rows]
    colors = ["#E63946" if cid == "venezuela_1967" else "#457B9D" for cid in labels]

    fig, ax = plt.subplots(figsize=(10, 4.8))
    if not values:
        ax.text(
            0.5,
            0.5,
            "No hay PGA (g) registrada en casos seleccionados",
            ha="center",
            va="center",
        )
        ax.axis("off")
        fig.tight_layout()
        return fig

    ax.bar(labels, values, color=colors)
    ax.set_title("Comparativa PGA agregada (g) por caso")
    ax.set_ylabel("PGA (g)")
    ax.tick_params(axis="x", rotation=45)
    if "venezuela_1967" in labels:
        fig.text(
            0.5,
            0.01,
            "1967: estimaciones NAS sin acelerogramas fuertes — no usar para calibrar 2026",
            ha="center",
            fontsize=8,
            color="#B00020",
        )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return fig


def _pga_summary_table(
    case_ids: list[str], case_lookup: dict[str, dict[str, Any]]
) -> list[list[str | float | int]]:
    rows = _pga_summary_rows(case_ids, case_lookup)
    return [
        [case_id, round(pga_g, 4), mmi_intensity, station_count, measurement_quality]
        for case_id, pga_g, mmi_intensity, station_count, measurement_quality in rows
    ]


def _pga_station_rows(
    case_ids: list[str], case_lookup: dict[str, dict[str, Any]]
) -> list[tuple[str, str, float, float | None, float | None, str, str, str, str]]:
    rows: list[tuple[str, str, float, float | None, float | None, str, str, str, str]] = []
    for case_id in case_ids:
        case = case_lookup.get(case_id)
        if not case:
            continue
        seismic = _read_path(case, ("advanced_features", "seismic"))
        if not isinstance(seismic, dict):
            continue
        estimates = seismic.get("pga_station_estimates")
        if not isinstance(estimates, list):
            continue
        for est in estimates:
            if not isinstance(est, dict):
                continue
            location = est.get("location")
            pga_g = est.get("pga_g")
            if not isinstance(location, str) or not isinstance(pga_g, (int, float)):
                continue
            pga_min = est.get("pga_g_min")
            pga_max = est.get("pga_g_max")
            rows.append(
                (
                    case_id,
                    location,
                    float(pga_g),
                    float(pga_min) if isinstance(pga_min, (int, float)) else None,
                    float(pga_max) if isinstance(pga_max, (int, float)) else None,
                    str(est.get("site_class", "")) if isinstance(est.get("site_class"), str) else "",
                    str(est.get("estimate_method", ""))
                    if isinstance(est.get("estimate_method"), str)
                    else "",
                    str(est.get("source", "")) if isinstance(est.get("source"), str) else "",
                    str(est.get("notes", "")) if isinstance(est.get("notes"), str) else "",
                )
            )
    rows.sort(key=lambda row: row[2], reverse=True)
    return rows


def _plot_pga_station_estimates(case_ids: list[str], case_lookup: dict[str, dict[str, Any]]):
    import matplotlib.pyplot as plt

    rows = _pga_station_rows(case_ids, case_lookup)
    labels = [f"{case_id}: {location[:28]}" for case_id, location, *_ in rows]
    values = [pga_g for _, _, pga_g, _, _, _, _, _, _ in rows]
    yerr_lower: list[float] = []
    yerr_upper: list[float] = []
    for _, _, pga_g, pga_min, pga_max, *_ in rows:
        if pga_min is not None and pga_max is not None:
            yerr_lower.append(max(0.0, pga_g - pga_min))
            yerr_upper.append(max(0.0, pga_max - pga_g))
        else:
            yerr_lower.append(0.0)
            yerr_upper.append(0.0)

    fig, ax = plt.subplots(figsize=(10, max(4.8, 0.45 * len(values) + 1.5)))
    if not values:
        ax.text(
            0.5,
            0.5,
            "No hay estimaciones PGA por estacion en casos seleccionados",
            ha="center",
            va="center",
        )
        ax.axis("off")
        fig.tight_layout()
        return fig

    y_pos = list(range(len(values)))
    ax.barh(y_pos, values, xerr=[yerr_lower, yerr_upper], color="#2A9D8F", capsize=3)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("PGA (g)")
    ax.set_title("Estimaciones PGA por zona/estacion (NAS Sozen 1968 y fuentes)")
    if any(case_id == "venezuela_1967" for case_id, *_ in rows):
        fig.text(
            0.5,
            0.01,
            "1967: estimaciones indirectas — sesgo metodologico/sitio; no calibrar modelos forward",
            ha="center",
            fontsize=8,
            color="#B00020",
        )
    ax.invert_yaxis()
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return fig


def _pga_station_table(
    case_ids: list[str], case_lookup: dict[str, dict[str, Any]]
) -> list[list[str | float]]:
    rows = _pga_station_rows(case_ids, case_lookup)
    return [
        [
            case_id,
            location,
            round(pga_g, 4),
            round(pga_min, 4) if pga_min is not None else "",
            round(pga_max, 4) if pga_max is not None else "",
            site_class,
            estimate_method,
            source,
            notes,
        ]
        for case_id, location, pga_g, pga_min, pga_max, site_class, estimate_method, source, notes in rows
    ]


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


def _risk_rows(case_ids: list[str], case_lookup: dict[str, dict[str, Any]]) -> list[tuple[str, float, str]]:
    rows: list[tuple[str, float, str]] = []
    for case_id in case_ids:
        case = case_lookup.get(case_id)
        if not case:
            continue
        risk_model = case.get("compound_risk_model", {})
        score = risk_model.get("risk_score_total")
        category = risk_model.get("risk_category")
        if isinstance(score, (int, float)) and isinstance(category, str):
            rows.append((case_id, float(score), category))
    rows.sort(key=lambda row: row[1], reverse=True)
    return rows


def _plot_risk_score_total(case_ids: list[str], case_lookup: dict[str, dict[str, Any]]):
    import matplotlib.pyplot as plt

    rows = _risk_rows(case_ids, case_lookup)
    labels = [row[0] for row in rows]
    scores = [row[1] for row in rows]

    fig, ax = plt.subplots(figsize=(10, 4.8))
    if not scores:
        ax.text(0.5, 0.5, "No risk scores found", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        return fig

    ax.bar(labels, scores, color="#3A86FF")
    ax.set_title("Comparativa: risk_score_total (Fase 4)")
    ax.set_ylabel("Risk score total")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    return fig


def _plot_risk_category_distribution(case_ids: list[str], case_lookup: dict[str, dict[str, Any]]):
    import matplotlib.pyplot as plt

    rows = _risk_rows(case_ids, case_lookup)
    categories = ["riesgo_bajo", "riesgo_medio", "riesgo_alto", "riesgo_critico"]
    counts = {key: 0 for key in categories}
    for _, _, category in rows:
        if category in counts:
            counts[category] += 1

    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    if sum(counts.values()) == 0:
        ax.text(0.5, 0.5, "No risk categories found", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        return fig

    ax.bar(list(counts.keys()), list(counts.values()), color="#FF006E")
    ax.set_title("Distribucion por risk_category (Fase 4)")
    ax.set_ylabel("Numero de casos")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    return fig


def _risk_summary_table(case_ids: list[str], case_lookup: dict[str, dict[str, Any]]) -> list[list[str | float]]:
    rows = _risk_rows(case_ids, case_lookup)
    return [[case_id, round(score, 2), category] for case_id, score, category in rows]


GEOLOGY_CONTEXT_TYPES: dict[str, str] = {
    "margen_subduccion": "Margen de subduccion",
    "falla_deslizamiento": "Falla de deslizamiento / transformante",
    "cuenca_lacustre": "Cuenca lacustre",
    "cuenca_sedimentaria": "Cuenca sedimentaria / aluvial",
    "intermontano": "Valle intermontano",
    "costero": "Entorno costero",
    "otro": "Otro contexto",
}


def _classify_geology_context(context: str) -> str:
    text = context.lower()
    if any(token in text for token in ("subduccion", "subduction", "megathrust")):
        return "margen_subduccion"
    if any(token in text for token in ("lacustre", "lago antiguo")):
        return "cuenca_lacustre"
    if any(
        token in text
        for token in ("transformante", "strike-slip", "falla de", "sistema de falla", "fallas activas")
    ):
        return "falla_deslizamiento"
    if "intermontano" in text or "valles" in text:
        return "intermontano"
    if any(token in text for token in ("coster", "costa", "planicies costeras")):
        return "costero"
    if any(token in text for token in ("cuenca", "sediment", "aluvial", "relleno")):
        return "cuenca_sedimentaria"
    return "otro"


def _geology_rows(
    case_ids: list[str],
    case_lookup: dict[str, dict[str, Any]],
    context_filter: str = "todos",
) -> list[tuple[str, str, str, float | None, str, str]]:
    rows: list[tuple[str, str, str, float | None, str, str]] = []
    for case_id in case_ids:
        case = case_lookup.get(case_id)
        if not case:
            continue
        context = _read_path(
            case, ("advanced_features", "geological_geotechnical", "location_geology_context")
        )
        if not isinstance(context, str) or not context.strip():
            continue
        context_type = _classify_geology_context(context)
        if context_filter != "todos" and context_type != context_filter:
            continue
        lithology = _read_path(case, ("advanced_features", "geological_geotechnical", "lithology"))
        vs30 = _read_path(case, ("advanced_features", "geological_geotechnical", "vs30_m_per_s"))
        risk_category = _read_path(case, ("compound_risk_model", "risk_category"))
        rows.append(
            (
                case_id,
                context_type,
                context,
                float(vs30) if isinstance(vs30, (int, float)) else None,
                str(lithology) if isinstance(lithology, str) else "",
                str(risk_category) if isinstance(risk_category, str) else "",
            )
        )
    rows.sort(key=lambda row: (row[1], row[0]))
    return rows


def _plot_geology_context_distribution(
    case_ids: list[str],
    case_lookup: dict[str, dict[str, Any]],
    context_filter: str,
):
    import matplotlib.pyplot as plt

    rows = _geology_rows(case_ids, case_lookup, context_filter="todos")
    if context_filter != "todos":
        rows = [row for row in rows if row[1] == context_filter]

    counts: dict[str, int] = {key: 0 for key in GEOLOGY_CONTEXT_TYPES}
    for _, context_type, *_ in rows:
        counts[context_type] = counts.get(context_type, 0) + 1

    labels = [GEOLOGY_CONTEXT_TYPES[key] for key in counts if counts[key] > 0]
    values = [counts[key] for key in counts if counts[key] > 0]

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    if not values:
        ax.text(0.5, 0.5, "No geology context data found", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        return fig

    ax.bar(labels, values, color="#2A9D8F")
    ax.set_title("Distribucion por tipo de contexto geologico")
    ax.set_ylabel("Numero de casos")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    return fig


def _geology_context_table(
    case_ids: list[str],
    case_lookup: dict[str, dict[str, Any]],
    context_filter: str,
) -> list[list[str | float]]:
    rows = _geology_rows(case_ids, case_lookup, context_filter)
    return [
        [
            case_id,
            GEOLOGY_CONTEXT_TYPES.get(context_type, context_type),
            context,
            vs30 if vs30 is not None else "",
            lithology,
            risk_category,
        ]
        for case_id, context_type, context, vs30, lithology, risk_category in rows
    ]


def _string_list_or_empty(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if isinstance(item, str) and str(item).strip()]


def _joined(value: list[str]) -> str:
    return ", ".join(value)


def _extract_plate_choices(case_lookup: dict[str, dict[str, Any]]) -> list[tuple[str, str]]:
    unique_plates: set[str] = set()
    for case in case_lookup.values():
        plates = _read_path(
            case, ("advanced_features", "geological_geotechnical", "nearby_tectonic_plates")
        )
        unique_plates.update(_string_list_or_empty(plates))
    return [("Todas las placas", "todos")] + [(plate, plate) for plate in sorted(unique_plates)]


def _fault_feature_rows(
    case_ids: list[str],
    case_lookup: dict[str, dict[str, Any]],
    plate_filter: str,
) -> list[tuple[str, str, str, float | None, int, str]]:
    rows: list[tuple[str, str, str, float | None, int, str]] = []
    for case_id in case_ids:
        case = case_lookup.get(case_id)
        if not case:
            continue
        geo = _read_path(case, ("advanced_features", "geological_geotechnical"))
        if not isinstance(geo, dict):
            continue

        nearby_faults = _string_list_or_empty(geo.get("nearby_geological_faults"))
        nearby_plates = _string_list_or_empty(geo.get("nearby_tectonic_plates"))
        if plate_filter != "todos" and plate_filter not in nearby_plates:
            continue

        avg_activity = geo.get("faults_average_seismic_activity_events_per_year")
        relevant_events = geo.get("fault_linked_relevant_events")

        event_summaries: list[str] = []
        if isinstance(relevant_events, list):
            for event in relevant_events:
                if not isinstance(event, dict):
                    continue
                event_name = event.get("event_name")
                event_year = event.get("event_year")
                magnitude = event.get("magnitude_mw")
                linked_fault = event.get("linked_fault")
                if not isinstance(event_name, str):
                    continue
                summary = event_name
                if isinstance(event_year, int):
                    summary += f" ({event_year})"
                if isinstance(magnitude, (int, float)):
                    summary += f" Mw {float(magnitude):.1f}"
                if isinstance(linked_fault, str) and linked_fault.strip():
                    summary += f" - {linked_fault}"
                event_summaries.append(summary)

        rows.append(
            (
                case_id,
                _joined(nearby_faults),
                _joined(nearby_plates),
                float(avg_activity) if isinstance(avg_activity, (int, float)) else None,
                len(event_summaries),
                " | ".join(event_summaries),
            )
        )

    rows.sort(key=lambda row: row[0])
    return rows


def _plot_fault_activity(
    case_ids: list[str],
    case_lookup: dict[str, dict[str, Any]],
    plate_filter: str,
):
    import matplotlib.pyplot as plt

    rows = _fault_feature_rows(case_ids, case_lookup, plate_filter)
    labels = [row[0] for row in rows if row[3] is not None]
    values = [float(row[3]) for row in rows if row[3] is not None]

    fig, ax = plt.subplots(figsize=(10, 4.8))
    if not values:
        ax.text(0.5, 0.5, "No fault activity values found", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        return fig

    ax.bar(labels, values, color="#457B9D")
    ax.set_title("Actividad sismica promedio en fallas proximas")
    ax.set_ylabel("Eventos/anio")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    return fig


def _fault_feature_table(
    case_ids: list[str],
    case_lookup: dict[str, dict[str, Any]],
    plate_filter: str,
) -> list[list[str | float | int]]:
    rows = _fault_feature_rows(case_ids, case_lookup, plate_filter)
    return [
        [
            case_id,
            nearby_faults,
            nearby_plates,
            avg_activity if avg_activity is not None else "",
            linked_events_count,
            linked_events,
        ]
        for case_id, nearby_faults, nearby_plates, avg_activity, linked_events_count, linked_events in rows
    ]


def build_interface():
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from international_calculation_workflow import mount_international_calculation_panel
    from layer_a.ui import mount_layer_a_panel
    from layer_b.ui import mount_layer_b_panel
    from layer_c.ui import mount_layer_c_panel
    from venezuela_projection_workflow import mount_venezuela_projection_panel

    import gradio as gr

    cases = _load_case_library()
    case_lookup = _build_case_lookup(cases)
    phase5_catalog = _load_phase5_models_catalog()
    case_ids = sorted(case_lookup.keys())
    metric_labels = list(METRICS.keys())

    default_cases = case_ids[: min(5, len(case_ids))]
    default_metric = "Magnitud Mw"
    default_x = "Magnitud Mw"
    default_y = "Replicas (conteo)"
    default_projection_forward_days = 8
    default_projection_as_of_date = date.today().isoformat()
    default_projection_scenario = "base"
    default_projection_max_magnitude = 6.0
    default_validation_days = 8
    geology_filter_choices = [("Todos los tipos", "todos")] + [
        (label, key) for key, label in GEOLOGY_CONTEXT_TYPES.items()
    ]
    tectonic_plate_choices = _extract_plate_choices(case_lookup)
    phase5_domain_choices = _phase5_domain_choices(phase5_catalog)

    with gr.Blocks(title="EarthquakeAnalysis") as demo:
        with gr.Tabs():
            with gr.Tab("Proyección Venezuela 2026"):
                wf_load_inputs, wf_load_outputs, _wf_run = mount_venezuela_projection_panel(
                    gr,
                    case_ids,
                    case_lookup,
                    default_projection_as_of_date,
                    default_projection_forward_days,
                    default_validation_days,
                    default_projection_max_magnitude,
                    30,
                    _similarity_stats,
                    _similarity_summary_table,
                    _hindcast_certainty_table,
                    _parse_as_of_date,
                )

            with gr.Tab("Calculo y Estimacion Internacional"):
                mount_international_calculation_panel(gr, default_projection_as_of_date)

            with gr.Tab("Capa C - Analisis H04 del evento"):
                mount_layer_c_panel(gr)

            with gr.Tab("Análisis comparativo (Fases 1-5)"):
                gr.Markdown("## Graficas comparativas de `case_library/`")
                gr.Markdown(
                    "Selecciona casos y metricas para comparar magnitudes, profundidad, variables de Fase 3 "
                    "y contexto geologico de localizacion."
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
                    geology_context_filter = gr.Dropdown(
                        choices=geology_filter_choices,
                        value="todos",
                        label="Filtro por tipo de contexto geologico",
                    )
                    tectonic_plate_filter = gr.Dropdown(
                        choices=tectonic_plate_choices,
                        value="todos",
                        label="Filtro tematico por placa tectonica proxima",
                    )
                    phase5_domain_filter = gr.Dropdown(
                        choices=phase5_domain_choices,
                        value="todos",
                        label="Filtro Fase 5 por dominio de modelos",
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
                with gr.Row():
                    risk_score_plot = gr.Plot(label="Comparativa de risk_score_total")
                    risk_category_plot = gr.Plot(label="Distribucion de risk_category")
                risk_table = gr.Dataframe(
                    headers=["case_id", "risk_score_total", "risk_category"],
                    datatype=["str", "number", "str"],
                    label="Resumen de riesgo compuesto por caso",
                    interactive=False,
                )
                with gr.Row():
                    geology_context_plot = gr.Plot(
                        label="Distribucion por tipo de contexto geologico (location_geology_context)"
                    )
                    geology_context_table = gr.Dataframe(
                        headers=[
                            "case_id",
                            "tipo_contexto_geologico",
                            "location_geology_context",
                            "vs30_m_per_s",
                            "litologia",
                            "risk_category",
                        ],
                        datatype=["str", "str", "str", "number", "str", "str"],
                        label="Tabla tematica de contexto geologico por localizacion",
                        interactive=False,
                    )
                with gr.Row():
                    fault_activity_plot = gr.Plot(
                        label="Actividad sismica promedio en fallas geologicas proximas"
                    )
                    fault_features_table = gr.Dataframe(
                        headers=[
                            "case_id",
                            "nearby_geological_faults",
                            "nearby_tectonic_plates",
                            "faults_average_seismic_activity_events_per_year",
                            "fault_linked_relevant_events_count",
                            "fault_linked_relevant_events_summary",
                        ],
                        datatype=["str", "str", "str", "number", "number", "str"],
                        label="Tabla tematica de fallas geologicas, placas y eventos vinculados",
                        interactive=False,
                    )
                phase5_models_table = gr.Dataframe(
                    headers=["dominio", "modelo_recomendado", "n_modelos_en_dominio"],
                    datatype=["str", "str", "number"],
                    label="Fase 5: catalogo de modelos recomendados por dominio",
                    interactive=False,
                )
                phase5_domain_plot = gr.Plot(
                    label="Fase 5: conteo de modelos recomendados por dominio"
                )
                gr.Markdown(
                    "**Analisis PGA:** compara `pga_g` agregada por caso y, cuando exista, "
                    "`pga_station_estimates[]` (p. ej. `venezuela_1967` NAS Sozen 1968)."
                )
                pga_bias_notice = gr.Markdown(label="Advertencia sesgo PGA")
                international_catalog_notice = gr.Markdown(
                    label="Catalogos internacionales 2026-06-24"
                )
                with gr.Row():
                    pga_summary_plot = gr.Plot(label="Comparativa PGA agregada (g) por caso")
                    pga_station_plot = gr.Plot(
                        label="Estimaciones PGA por zona/estacion (con rango min-max si aplica)"
                    )
                with gr.Row():
                    pga_summary_table = gr.Dataframe(
                        headers=[
                            "case_id",
                            "pga_g",
                            "mmi_intensity",
                            "station_estimates_count",
                            "pga_measurement_quality",
                        ],
                        datatype=["str", "number", "str", "number", "str"],
                        label="Resumen PGA por caso",
                        interactive=False,
                    )
                    pga_station_table = gr.Dataframe(
                        headers=[
                            "case_id",
                            "location",
                            "pga_g",
                            "pga_g_min",
                            "pga_g_max",
                            "site_class",
                            "estimate_method",
                            "source",
                            "notes",
                        ],
                        datatype=["str", "str", "number", "number", "number", "str", "str", "str", "str"],
                        label="Detalle PGA por estacion/zona",
                        interactive=False,
                    )

                def _render(
                    case_values: list[str],
                    bar_value: str,
                    x_value: str,
                    y_value: str,
                    horizon_value: int,
                    geology_filter_value: str,
                    tectonic_plate_filter_value: str,
                    phase5_domain_filter_value: str,
                ):
                    use_cases = case_values or case_ids
                    return (
                        _plot_bar(use_cases, bar_value, case_lookup),
                        _plot_scatter(use_cases, x_value, y_value, case_lookup),
                        _plot_similarity_probability(use_cases, int(horizon_value), case_lookup),
                        _similarity_summary_table(use_cases, int(horizon_value), case_lookup),
                        _plot_risk_score_total(use_cases, case_lookup),
                        _plot_risk_category_distribution(use_cases, case_lookup),
                        _risk_summary_table(use_cases, case_lookup),
                        _plot_geology_context_distribution(
                            use_cases, case_lookup, geology_filter_value
                        ),
                        _geology_context_table(use_cases, case_lookup, geology_filter_value),
                        _plot_fault_activity(use_cases, case_lookup, tectonic_plate_filter_value),
                        _fault_feature_table(use_cases, case_lookup, tectonic_plate_filter_value),
                        _phase5_catalog_table(phase5_catalog, phase5_domain_filter_value),
                        _plot_phase5_domain_counts(phase5_catalog, phase5_domain_filter_value),
                        _plot_pga_summary(use_cases, case_lookup),
                        _plot_pga_station_estimates(use_cases, case_lookup),
                        _pga_summary_table(use_cases, case_lookup),
                        _pga_station_table(use_cases, case_lookup),
                        _pga_calibration_bias_notice(use_cases, case_lookup),
                        _international_catalog_notice(use_cases),
                    )

                update_button.click(
                    _render,
                    inputs=[
                        selected_cases,
                        bar_metric,
                        x_metric,
                        y_metric,
                        horizon_days,
                        geology_context_filter,
                        tectonic_plate_filter,
                        phase5_domain_filter,
                    ],
                    outputs=[
                        bar_plot,
                        scatter_plot,
                        probability_plot,
                        probability_table,
                        risk_score_plot,
                        risk_category_plot,
                        risk_table,
                        geology_context_plot,
                        geology_context_table,
                        fault_activity_plot,
                        fault_features_table,
                        phase5_models_table,
                        phase5_domain_plot,
                        pga_summary_plot,
                        pga_station_plot,
                        pga_summary_table,
                        pga_station_table,
                        pga_bias_notice,
                        international_catalog_notice,
                    ],
                )

                demo.load(
                    _render,
                    inputs=[
                        selected_cases,
                        bar_metric,
                        x_metric,
                        y_metric,
                        horizon_days,
                        geology_context_filter,
                        tectonic_plate_filter,
                        phase5_domain_filter,
                    ],
                    outputs=[
                        bar_plot,
                        scatter_plot,
                        probability_plot,
                        probability_table,
                        risk_score_plot,
                        risk_category_plot,
                        risk_table,
                        geology_context_plot,
                        geology_context_table,
                        fault_activity_plot,
                        fault_features_table,
                        phase5_models_table,
                        phase5_domain_plot,
                        pga_summary_plot,
                        pga_station_plot,
                        pga_summary_table,
                        pga_station_table,
                        pga_bias_notice,
                        international_catalog_notice,
                    ],
                )

            demo.load(
                _wf_run,
                inputs=wf_load_inputs,
                outputs=wf_load_outputs,
            )

            with gr.Tab("Capa A — Tectónica"):
                mount_layer_a_panel(gr)

            with gr.Tab("Capa B — Geofísica Ambiental"):
                mount_layer_b_panel(gr)

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
