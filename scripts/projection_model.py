#!/usr/bin/env python3
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any

MAGNITUDE_MIN_REFERENCE = 4.0
OMORI_C_DAYS = 1.0

PROJECTION_SCENARIOS: dict[str, dict[str, float | str]] = {
    "base": {
        "label": "Base (calibracion YAML)",
        "k_factor": 1.0,
        "b_offset": 0.0,
        "k_obs_below_target_factor": 1.0,
    },
    "conservador": {
        "label": "Conservador (Mmax observada por debajo del objetivo)",
        "k_factor": 0.82,
        "b_offset": 0.12,
        "k_obs_below_target_factor": 0.88,
    },
    "optimista": {
        "label": "Optimista (secuencia activa, mayor peso eventos grandes)",
        "k_factor": 1.08,
        "b_offset": -0.10,
        "k_obs_below_target_factor": 1.0,
    },
}

SCENARIO_CHOICES: list[tuple[str, str]] = [
    (str(spec["label"]), key) for key, spec in PROJECTION_SCENARIOS.items()
] + [("Calibrado (eventos históricos)", "calibrado")]

TARGET_CASE_ID = "venezuela_2026"


@dataclass(frozen=True)
class CalibrationResult:
    k_factor: float
    b_offset: float
    k_obs_below_target_factor: float
    mean_brier_score: float
    mean_certainty_percent: float
    training_case_ids: tuple[str, ...]


@dataclass(frozen=True)
class ForwardProjectionRow:
    case_id: str
    scenario: str
    as_of_date: str
    elapsed_days_from_main: int
    forward_days: int
    horizon_days_from_main: int
    magnitude_target_mw: float
    omori_K: float
    b_value: float
    additional_expected_aftershocks: float
    expected_max_magnitude_mw: float
    expected_max_magnitude_capped_mw: float
    probability_m_ge_target: float
    observed_max_magnitude_mw: float | None
    linear_regression_slope_prob_per_day: float
    linear_regression_r2: float


@dataclass(frozen=True)
class HindcastCertaintyRow:
    case_id: str
    scenario: str
    model_name: str
    validation_days: int
    magnitude_target_mw: float
    predicted_probability_m_ge_target: float
    observed_event_reached: bool
    observed_max_magnitude_mw: float | None
    brier_score: float
    certainty_percent: float
    certainty_delta_vs_venezuela_2026: float | None = None
    certainty_vs_venezuela_2026_percent: float | None = None


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def observed_horizon_days(similarity: dict[str, Any]) -> float:
    main_event_date = similarity.get("main_event_date")
    sequence_end_date = similarity.get("sequence_end_date")
    if isinstance(main_event_date, str) and isinstance(sequence_end_date, str):
        main_dt = parse_date(main_event_date)
        end_dt = parse_date(sequence_end_date)
        horizon = float((end_dt - main_dt).days)
        if horizon > 0:
            return horizon

    highest_events = similarity.get("highest_magnitude_events", [])
    if isinstance(highest_events, list):
        max_day = max(
            (
                int(ev.get("days_after_main"))
                for ev in highest_events
                if isinstance(ev, dict) and isinstance(ev.get("days_after_main"), int)
            ),
            default=30,
        )
        return float(max_day if max_day > 0 else 30)
    return 30.0


def cum_omori(t_days: float, K: float, p: float, c_days: float = OMORI_C_DAYS) -> float:
    if t_days <= 0:
        return 0.0
    if abs(p - 1.0) < 1e-9:
        return K * math.log((t_days + c_days) / c_days)
    return K * (((t_days + c_days) ** (1.0 - p)) - (c_days ** (1.0 - p))) / (1.0 - p)


def calibrate_omori(
    n_observed: float, p: float, horizon_days: float, c_days: float = OMORI_C_DAYS
) -> float:
    if horizon_days <= 0:
        return 0.0
    if abs(p - 1.0) < 1e-9:
        denom = math.log((horizon_days + c_days) / c_days)
        return n_observed / denom if denom > 0 else 0.0
    denom = (((horizon_days + c_days) ** (1.0 - p)) - (c_days ** (1.0 - p))) / (1.0 - p)
    return n_observed / denom if denom > 0 else 0.0


def max_observed_magnitude_mw(similarity: dict[str, Any], as_of_date: date) -> float | None:
    main_event_date = similarity.get("main_event_date")
    if not isinstance(main_event_date, str):
        return None
    main_dt = parse_date(main_event_date)
    highest_events = similarity.get("highest_magnitude_events", [])
    if not isinstance(highest_events, list):
        return None

    max_mw: float | None = None
    for ev in highest_events:
        if not isinstance(ev, dict):
            continue
        event_date = ev.get("event_date")
        magnitude_mw = ev.get("magnitude_mw")
        if not isinstance(event_date, str) or not isinstance(magnitude_mw, (int, float)):
            continue
        ev_dt = parse_date(event_date)
        if main_dt <= ev_dt <= as_of_date:
            max_mw = magnitude_mw if max_mw is None else max(max_mw, float(magnitude_mw))
    return max_mw


def max_observed_magnitude_until_day(
    similarity: dict[str, Any], validation_days: int
) -> float | None:
    highest_events = similarity.get("highest_magnitude_events", [])
    if not isinstance(highest_events, list):
        return None

    max_mw: float | None = None
    for ev in highest_events:
        if not isinstance(ev, dict):
            continue
        day_value = ev.get("days_after_main")
        magnitude_mw = ev.get("magnitude_mw")
        if not isinstance(day_value, int) or not isinstance(magnitude_mw, (int, float)):
            continue
        if day_value <= validation_days:
            max_mw = float(magnitude_mw) if max_mw is None else max(max_mw, float(magnitude_mw))
    return max_mw


def observed_event_reached_until_day(
    similarity: dict[str, Any], validation_days: int, magnitude_target_mw: float
) -> bool:
    highest_events = similarity.get("highest_magnitude_events", [])
    if not isinstance(highest_events, list):
        return False
    for ev in highest_events:
        if not isinstance(ev, dict):
            continue
        day_value = ev.get("days_after_main")
        magnitude_mw = ev.get("magnitude_mw")
        if not isinstance(day_value, int) or not isinstance(magnitude_mw, (int, float)):
            continue
        if day_value <= validation_days and float(magnitude_mw) >= float(magnitude_target_mw):
            return True
    return False


def apply_scenario_parameters(
    base_K: float,
    base_b: float,
    scenario_key: str,
    magnitude_target_mw: float,
    observed_max_mw: float | None,
    calibration_override: tuple[float, float, float] | None = None,
) -> tuple[float, float]:
    if calibration_override is not None:
        k_factor, b_offset, obs_factor = calibration_override
    else:
        spec = PROJECTION_SCENARIOS.get(scenario_key, PROJECTION_SCENARIOS["base"])
        k_factor = float(spec["k_factor"])
        b_offset = float(spec["b_offset"])
        obs_factor = float(spec["k_obs_below_target_factor"])
    if observed_max_mw is not None and observed_max_mw < magnitude_target_mw - 0.5:
        k_factor *= obs_factor
    adjusted_K = base_K * k_factor
    adjusted_b = min(max(base_b + b_offset, 0.75), 1.20)
    return adjusted_K, adjusted_b


def _hindcast_metrics_for_case(
    seismic: dict[str, Any],
    similarity: dict[str, Any],
    validation_days: int,
    magnitude_target_mw: float,
    param_override: tuple[float, float, float] | None = None,
    scenario_key: str = "base",
) -> tuple[float, bool, float | None, float] | None:
    aftershock_count = seismic.get("aftershock_count")
    omori_p = seismic.get("omori_decay_p")
    b_value = seismic.get("gutenberg_richter_b_value")
    if not (
        isinstance(aftershock_count, (int, float))
        and isinstance(omori_p, (int, float))
        and isinstance(b_value, (int, float))
    ):
        return None

    p = float(omori_p)
    base_b = float(b_value)
    observed_horizon = observed_horizon_days(similarity)
    base_K = calibrate_omori(float(aftershock_count), p, observed_horizon)
    observed_max_window = max_observed_magnitude_until_day(similarity, validation_days)
    K, b = apply_scenario_parameters(
        base_K,
        base_b,
        scenario_key,
        float(magnitude_target_mw),
        observed_max_window,
        calibration_override=param_override,
    )
    n_validation = max(0.0, cum_omori(float(validation_days), K, p) - cum_omori(0.0, K, p))
    prob = probability_m_ge(n_validation, float(magnitude_target_mw), b)
    observed_reached = observed_event_reached_until_day(
        similarity, validation_days, float(magnitude_target_mw)
    )
    y = 1.0 if observed_reached else 0.0
    brier = (prob - y) ** 2
    return prob, observed_reached, observed_max_window, brier


def calibrate_from_hindcast(
    case_ids: list[str],
    case_lookup: dict[str, dict[str, Any]],
    validation_days: int,
    magnitude_target_mw: float,
    exclude_case_ids: tuple[str, ...] = (TARGET_CASE_ID,),
) -> CalibrationResult | None:
    training_ids = [cid for cid in case_ids if cid not in exclude_case_ids]
    if not training_ids:
        return None

    k_grid = (0.75, 0.82, 0.88, 0.94, 1.0, 1.06, 1.12)
    b_grid = (-0.12, -0.06, 0.0, 0.06, 0.12)
    obs_grid = (0.88, 1.0)

    best_brier = float("inf")
    best_params = (1.0, 0.0, 1.0)

    for k_factor in k_grid:
        for b_offset in b_grid:
            for obs_factor in obs_grid:
                briers: list[float] = []
                for case_id in training_ids:
                    case = case_lookup.get(case_id)
                    if not case:
                        continue
                    seismic = case.get("advanced_features", {}).get("seismic", {})
                    similarity = case.get("similar_magnitude_probability_dates", {})
                    if not isinstance(seismic, dict) or not isinstance(similarity, dict):
                        continue
                    metrics = _hindcast_metrics_for_case(
                        seismic,
                        similarity,
                        validation_days,
                        magnitude_target_mw,
                        param_override=(k_factor, b_offset, obs_factor),
                    )
                    if metrics is not None:
                        briers.append(metrics[3])
                if not briers:
                    continue
                mean_brier = sum(briers) / len(briers)
                if mean_brier < best_brier:
                    best_brier = mean_brier
                    best_params = (k_factor, b_offset, obs_factor)

    mean_certainty = (1.0 - best_brier) * 100.0
    return CalibrationResult(
        k_factor=best_params[0],
        b_offset=best_params[1],
        k_obs_below_target_factor=best_params[2],
        mean_brier_score=round(best_brier, 4),
        mean_certainty_percent=round(mean_certainty, 2),
        training_case_ids=tuple(training_ids),
    )


def probability_m_ge(
    n_additional: float,
    magnitude_target_mw: float,
    b_value: float,
    magnitude_min_reference: float = MAGNITUDE_MIN_REFERENCE,
) -> float:
    n_ge = n_additional * (
        10 ** (-b_value * (float(magnitude_target_mw) - magnitude_min_reference))
    )
    return 1.0 - math.exp(-max(n_ge, 0.0))


def expected_max_magnitude_mw(
    n_additional: float,
    b_value: float,
    magnitude_min_reference: float = MAGNITUDE_MIN_REFERENCE,
) -> float:
    return magnitude_min_reference + (math.log10(max(n_additional, 1e-6)) / b_value)


def forward_daily_probabilities(
    elapsed_days: int,
    forward_days: int,
    K: float,
    p: float,
    magnitude_target_mw: float,
    b_value: float,
    c_days: float = OMORI_C_DAYS,
    magnitude_min_reference: float = MAGNITUDE_MIN_REFERENCE,
) -> list[float]:
    probs: list[float] = []
    for offset in range(1, forward_days + 1):
        day = elapsed_days + offset
        n_day = max(0.0, cum_omori(float(day), K, p, c_days))
        probs.append(
            probability_m_ge(n_day, magnitude_target_mw, b_value, magnitude_min_reference)
        )
    return probs


def build_forward_projection_row(
    case_id: str,
    seismic: dict[str, Any],
    similarity: dict[str, Any],
    as_of_date: date,
    forward_days: int,
    magnitude_target_mw: float,
    scenario_key: str = "base",
    calibration_override: tuple[float, float, float] | None = None,
) -> ForwardProjectionRow | None:
    aftershock_count = seismic.get("aftershock_count")
    omori_p = seismic.get("omori_decay_p")
    b_value = seismic.get("gutenberg_richter_b_value")
    main_event_date = similarity.get("main_event_date")
    if not (
        isinstance(aftershock_count, (int, float))
        and isinstance(omori_p, (int, float))
        and isinstance(b_value, (int, float))
        and isinstance(main_event_date, str)
    ):
        return None

    main_dt = parse_date(main_event_date)
    elapsed_days = max(0, (as_of_date - main_dt).days)
    horizon_days = elapsed_days + int(forward_days)
    if forward_days <= 0:
        return None

    p = float(omori_p)
    base_b = float(b_value)
    observed_horizon = observed_horizon_days(similarity)
    base_K = calibrate_omori(float(aftershock_count), p, observed_horizon)
    observed_max_mw = max_observed_magnitude_mw(similarity, as_of_date)
    if calibration_override is not None:
        K, b = apply_scenario_parameters(
            base_K, base_b, scenario_key, float(magnitude_target_mw), observed_max_mw,
            calibration_override=calibration_override,
        )
    else:
        K, b = apply_scenario_parameters(
            base_K, base_b, scenario_key, float(magnitude_target_mw), observed_max_mw
        )

    n_additional = max(
        0.0,
        cum_omori(float(horizon_days), K, p) - cum_omori(float(elapsed_days), K, p),
    )
    expected_max_mw = expected_max_magnitude_mw(n_additional, b)
    expected_max_mw_capped = min(expected_max_mw, float(magnitude_target_mw))
    p_ge_target = probability_m_ge(n_additional, float(magnitude_target_mw), b)

    daily_probs = forward_daily_probabilities(
        elapsed_days,
        int(forward_days),
        K,
        p,
        float(magnitude_target_mw),
        b,
    )
    x_days = [float(elapsed_days + offset) for offset in range(1, forward_days + 1)]
    slope, _, r2 = _linear_regression(x_days, daily_probs)

    return ForwardProjectionRow(
        case_id=case_id,
        scenario=scenario_key,
        as_of_date=as_of_date.isoformat(),
        elapsed_days_from_main=elapsed_days,
        forward_days=int(forward_days),
        horizon_days_from_main=horizon_days,
        magnitude_target_mw=float(magnitude_target_mw),
        omori_K=round(K, 4),
        b_value=round(b, 4),
        additional_expected_aftershocks=round(n_additional, 2),
        expected_max_magnitude_mw=round(expected_max_mw, 2),
        expected_max_magnitude_capped_mw=round(expected_max_mw_capped, 2),
        probability_m_ge_target=round(p_ge_target, 4),
        observed_max_magnitude_mw=round(observed_max_mw, 2) if observed_max_mw is not None else None,
        linear_regression_slope_prob_per_day=round(slope, 6),
        linear_regression_r2=round(r2, 4),
    )


def build_forward_projection_rows(
    case_ids: list[str],
    case_lookup: dict[str, dict[str, Any]],
    as_of_date: date,
    forward_days: int,
    magnitude_target_mw: float,
    scenario_key: str = "base",
    calibration_override: tuple[float, float, float] | None = None,
) -> list[ForwardProjectionRow]:
    rows: list[ForwardProjectionRow] = []
    for case_id in case_ids:
        case = case_lookup.get(case_id)
        if not case:
            continue
        seismic = case.get("advanced_features", {}).get("seismic", {})
        similarity = case.get("similar_magnitude_probability_dates", {})
        if not isinstance(seismic, dict) or not isinstance(similarity, dict):
            continue
        row = build_forward_projection_row(
            case_id,
            seismic,
            similarity,
            as_of_date,
            forward_days,
            magnitude_target_mw,
            scenario_key,
            calibration_override=calibration_override,
        )
        if row is not None:
            rows.append(row)
    rows.sort(key=lambda row: row.probability_m_ge_target, reverse=True)
    return rows


def build_calibrated_forward_projection_row(
    case_lookup: dict[str, dict[str, Any]],
    calibration: CalibrationResult,
    as_of_date: date,
    forward_days: int,
    magnitude_target_mw: float,
    target_case_id: str = TARGET_CASE_ID,
) -> ForwardProjectionRow | None:
    case = case_lookup.get(target_case_id)
    if not case:
        return None
    seismic = case.get("advanced_features", {}).get("seismic", {})
    similarity = case.get("similar_magnitude_probability_dates", {})
    if not isinstance(seismic, dict) or not isinstance(similarity, dict):
        return None
    override = (
        calibration.k_factor,
        calibration.b_offset,
        calibration.k_obs_below_target_factor,
    )
    return build_forward_projection_row(
        target_case_id,
        seismic,
        similarity,
        as_of_date,
        forward_days,
        magnitude_target_mw,
        scenario_key="calibrado",
        calibration_override=override,
    )


def build_hindcast_certainty_rows(
    case_ids: list[str],
    case_lookup: dict[str, dict[str, Any]],
    validation_days: int,
    magnitude_target_mw: float,
    scenario_key: str = "base",
    benchmark_case_id: str = TARGET_CASE_ID,
    calibration_override: tuple[float, float, float] | None = None,
    exclude_case_ids: tuple[str, ...] | None = None,
) -> list[HindcastCertaintyRow]:
    if validation_days <= 0:
        return []

    model_name = "Omori-Utsu + Gutenberg-Richter + Poisson (hindcast)"
    rows: list[HindcastCertaintyRow] = []
    filtered_ids = [
        cid for cid in case_ids
        if exclude_case_ids is None or cid not in exclude_case_ids
    ]

    def _compute_row(case_id: str) -> HindcastCertaintyRow | None:
        case = case_lookup.get(case_id)
        if not case:
            return None
        seismic = case.get("advanced_features", {}).get("seismic", {})
        similarity = case.get("similar_magnitude_probability_dates", {})
        if not isinstance(seismic, dict) or not isinstance(similarity, dict):
            return None

        metrics = _hindcast_metrics_for_case(
            seismic,
            similarity,
            validation_days,
            magnitude_target_mw,
            param_override=calibration_override,
            scenario_key=scenario_key,
        )
        if metrics is None:
            return None
        prob, observed_reached, observed_max_window, brier = metrics
        certainty_percent = (1.0 - brier) * 100.0

        return HindcastCertaintyRow(
            case_id=case_id,
            scenario=scenario_key,
            model_name=model_name,
            validation_days=int(validation_days),
            magnitude_target_mw=float(magnitude_target_mw),
            predicted_probability_m_ge_target=round(prob, 4),
            observed_event_reached=observed_reached,
            observed_max_magnitude_mw=(
                round(observed_max_window, 2) if observed_max_window is not None else None
            ),
            brier_score=round(brier, 4),
            certainty_percent=round(certainty_percent, 2),
        )

    for case_id in filtered_ids:
        row = _compute_row(case_id)
        if row is not None:
            rows.append(row)

    benchmark_row = _compute_row(benchmark_case_id)
    benchmark_certainty = benchmark_row.certainty_percent if benchmark_row is not None else None
    if benchmark_certainty is not None:
        rows = [
            replace(
                row,
                certainty_delta_vs_venezuela_2026=round(row.certainty_percent - benchmark_certainty, 2),
                certainty_vs_venezuela_2026_percent=round(
                    max(0.0, 100.0 - abs(row.certainty_percent - benchmark_certainty)),
                    2,
                ),
            )
            for row in rows
        ]

    rows.sort(key=lambda row: row.certainty_percent, reverse=True)
    return rows


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
