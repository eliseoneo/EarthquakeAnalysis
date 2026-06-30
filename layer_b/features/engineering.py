"""Ingeniería de features ambientales."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import numpy as np

from layer_b.models import EnvironmentalObservation, FeatureRecord


def _series_by_variable(
    observations: list[EnvironmentalObservation],
    region_code: str,
    variable: str,
) -> list[tuple[datetime, float]]:
    rows = [
        (o.datetime_utc, o.value)
        for o in observations
        if o.region_code == region_code and o.variable == variable
    ]
    return sorted(rows, key=lambda x: x[0])


def _values_in_window(
    series: list[tuple[datetime, float]],
    ref: datetime,
    start_offset: int,
    end_offset: int,
) -> list[float]:
    start = ref + timedelta(days=start_offset)
    end = ref + timedelta(days=end_offset)
    if start_offset > end_offset:
        start, end = end, start
    return [v for dt, v in series if start <= dt <= end]


def _safe_mean(values: list[float]) -> float | None:
    return float(np.mean(values)) if values else None


def _safe_std(values: list[float]) -> float | None:
    return float(np.std(values)) if len(values) > 1 else None


def _delta(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    return current - previous


def build_sst_features(
    observations: list[EnvironmentalObservation],
    region_code: str,
    ref: datetime,
) -> list[FeatureRecord]:
    series = _series_by_variable(observations, region_code, "sst")
    mean_7 = _safe_mean(_values_in_window(series, ref, -7, 0))
    mean_30 = _safe_mean(_values_in_window(series, ref, -30, 0))
    std_7 = _safe_std(_values_in_window(series, ref, -7, 0))
    mean_prev_7 = _safe_mean(_values_in_window(series, ref, -14, -7))
    mean_prev_30 = _safe_mean(_values_in_window(series, ref, -60, -30))
    baseline = _safe_mean(_values_in_window(series, ref, -365, -30))
    specs = [
        ("sst_mean_7d", mean_7, -7),
        ("sst_mean_30d", mean_30, -30),
        ("sst_std_7d", std_7, -7),
        ("sst_delta_7d", _delta(mean_7, mean_prev_7), -7),
        ("sst_delta_30d", _delta(mean_30, mean_prev_30), -30),
        ("sst_anomaly", _delta(mean_30, baseline), -30),
    ]
    return [
        FeatureRecord(
            region_code=region_code,
            reference_datetime_utc=ref,
            feature_name=name,
            feature_value=val,
            window_days=window,
            evidence_level="B" if val is not None else "C",
        )
        for name, val, window in specs
    ]


def build_pressure_features(
    observations: list[EnvironmentalObservation],
    region_code: str,
    ref: datetime,
) -> list[FeatureRecord]:
    series = _series_by_variable(observations, region_code, "pressure_hpa")
    mean_7 = _safe_mean(_values_in_window(series, ref, -7, 0))
    std_7 = _safe_std(_values_in_window(series, ref, -7, 0))
    val_0 = _safe_mean(_values_in_window(series, ref, 0, 0))
    val_24h = _safe_mean(_values_in_window(series, ref, -1, -1))
    val_72h = _safe_mean(_values_in_window(series, ref, -3, -3))
    baseline = _safe_mean(_values_in_window(series, ref, -90, -30))
    specs = [
        ("pressure_mean_7d", mean_7, -7),
        ("pressure_std_7d", std_7, -7),
        ("pressure_change_24h", _delta(val_0, val_24h), -1),
        ("pressure_change_72h", _delta(val_0, val_72h), -3),
        ("pressure_anomaly", _delta(mean_7, baseline), -7),
    ]
    return [
        FeatureRecord(
            region_code=region_code,
            reference_datetime_utc=ref,
            feature_name=name,
            feature_value=val,
            window_days=window,
            evidence_level="B" if val is not None else "C",
        )
        for name, val, window in specs
    ]


def build_rainfall_features(
    observations: list[EnvironmentalObservation],
    region_code: str,
    ref: datetime,
) -> list[FeatureRecord]:
    series = _series_by_variable(observations, region_code, "rainfall_mm")
    specs = [
        ("rain_acc_1d", _safe_mean(_values_in_window(series, ref, -1, 0)), -1),
        ("rain_acc_3d", sum(_values_in_window(series, ref, -3, 0)) or None, -3),
        ("rain_acc_7d", sum(_values_in_window(series, ref, -7, 0)) or None, -7),
        ("rain_acc_15d", sum(_values_in_window(series, ref, -15, 0)) or None, -15),
        ("rain_acc_30d", sum(_values_in_window(series, ref, -30, 0)) or None, -30),
    ]
    return [
        FeatureRecord(
            region_code=region_code,
            reference_datetime_utc=ref,
            feature_name=name,
            feature_value=float(val) if val is not None else None,
            window_days=window,
            evidence_level="B" if val is not None else "C",
        )
        for name, val, window in specs
    ]


def build_soil_moisture_features(
    observations: list[EnvironmentalObservation],
    region_code: str,
    ref: datetime,
) -> list[FeatureRecord]:
    series = _series_by_variable(observations, region_code, "soil_moisture")
    window_vals = _values_in_window(series, ref, -30, 0)
    prev_vals = _values_in_window(series, ref, -60, -30)
    mean_val = _safe_mean(window_vals)
    std_val = _safe_std(window_vals)
    baseline = _safe_mean(_values_in_window(series, ref, -365, -30))
    trend = _delta(mean_val, _safe_mean(prev_vals))
    specs = [
        ("soil_moisture_mean", mean_val, -30),
        ("soil_moisture_std", std_val, -30),
        ("soil_moisture_anomaly", _delta(mean_val, baseline), -30),
        ("soil_moisture_trend", trend, -30),
    ]
    return [
        FeatureRecord(
            region_code=region_code,
            reference_datetime_utc=ref,
            feature_name=name,
            feature_value=val,
            window_days=window,
            evidence_level="B" if val is not None else "C",
        )
        for name, val, window in specs
    ]


def build_earth_tide_features(
    observations: list[EnvironmentalObservation],
    region_code: str,
    ref: datetime,
) -> list[FeatureRecord]:
    series = _series_by_variable(observations, region_code, "earth_tide")
    vals = _values_in_window(series, ref, -7, 0)
    mean_val = _safe_mean(vals)
    max_val = max(vals) if vals else None
    gradient = _delta(max(vals) if vals else None, min(vals) if vals else None)
    stress = (mean_val or 0) * (gradient or 0) if mean_val is not None else None
    specs = [
        ("earth_tide_mean", mean_val, -7),
        ("earth_tide_max", max_val, -7),
        ("earth_tide_gradient", gradient, -7),
        ("earth_tide_stress_index", stress, -7),
    ]
    return [
        FeatureRecord(
            region_code=region_code,
            reference_datetime_utc=ref,
            feature_name=name,
            feature_value=val,
            window_days=window,
            evidence_level="C",
        )
        for name, val, window in specs
    ]


def build_all_features(
    observations: list[EnvironmentalObservation],
    region_code: str,
    ref: datetime,
) -> list[FeatureRecord]:
    builders = [
        build_sst_features,
        build_pressure_features,
        build_rainfall_features,
        build_soil_moisture_features,
        build_earth_tide_features,
    ]
    features: list[FeatureRecord] = []
    for builder in builders:
        features.extend(builder(observations, region_code, ref))
    return features


def features_to_dict_map(features: list[FeatureRecord]) -> dict[str, float]:
    out: dict[str, float] = {}
    for feat in features:
        if feat.feature_value is not None:
            out[feat.feature_name] = feat.feature_value
    return out
