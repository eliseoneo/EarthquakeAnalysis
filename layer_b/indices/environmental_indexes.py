"""Índices ambientales normalizados 0-100."""

from __future__ import annotations

from datetime import datetime

from layer_b.models import EnvironmentalIndexRecord, FeatureRecord


def _scale_0_100(value: float | None, low: float, high: float) -> float:
    if value is None:
        return 50.0
    if high == low:
        return 50.0
    scaled = (value - low) / (high - low) * 100.0
    return max(0.0, min(100.0, scaled))


def _feat_map(features: list[FeatureRecord]) -> dict[str, float]:
    return {
        f.feature_name: f.feature_value
        for f in features
        if f.feature_value is not None
    }


def compute_environmental_indexes(
    region_code: str,
    ref: datetime,
    features: list[FeatureRecord],
) -> EnvironmentalIndexRecord:
    fmap = _feat_map(features)

    sst_activity = _scale_0_100(fmap.get("sst_anomaly"), -2.0, 2.0)
    rainfall_stress = _scale_0_100(fmap.get("rain_acc_7d"), 0.0, 120.0)
    soil_saturation = _scale_0_100(fmap.get("soil_moisture_mean"), 0.2, 0.5)
    pressure_index = _scale_0_100(fmap.get("pressure_anomaly"), -10.0, 10.0)
    oceanic_anomaly = _scale_0_100(fmap.get("sst_delta_30d"), -2.0, 2.0)

    components = [sst_activity, rainfall_stress, soil_saturation, pressure_index, oceanic_anomaly]
    environmental_anomaly = sum(components) / len(components)

    evidence = "B"
    if fmap.get("sst_anomaly") is not None and fmap.get("rain_acc_7d") is not None:
        evidence = "B"
    else:
        evidence = "C"

    return EnvironmentalIndexRecord(
        region_code=region_code,
        reference_datetime_utc=ref,
        sst_activity_index=round(sst_activity, 2),
        rainfall_stress_index=round(rainfall_stress, 2),
        soil_saturation_index=round(soil_saturation, 2),
        atmospheric_pressure_index=round(pressure_index, 2),
        oceanic_anomaly_index=round(oceanic_anomaly, 2),
        environmental_anomaly_index=round(environmental_anomaly, 2),
        evidence_level=evidence,
    )
