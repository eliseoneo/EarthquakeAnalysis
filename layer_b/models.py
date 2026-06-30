"""Modelos Pydantic — Capa B Geofísica Ambiental."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from layer_b.formatting import format_datetime_utc


class EnvironmentalObservation(BaseModel):
    observation_id: str
    region_code: str
    datetime_utc: datetime
    domain: str
    variable: str
    value: float
    unit: str
    source: str
    quality_flag: str = "B"

    def to_flat_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        data["datetime_utc"] = format_datetime_utc(self.datetime_utc)
        return data


class FeatureRecord(BaseModel):
    region_code: str
    reference_datetime_utc: datetime
    feature_name: str
    feature_value: float | None
    window_days: int | None = None
    evidence_level: str = "C"

    def to_flat_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        data["reference_datetime_utc"] = format_datetime_utc(self.reference_datetime_utc)
        return data


class CorrelationResult(BaseModel):
    region_code: str
    variable_x: str
    variable_y: str
    method: str
    coefficient: float | None
    p_value: float | None
    sample_size: int
    evidence_level: str


class EnvironmentalIndexRecord(BaseModel):
    region_code: str
    reference_datetime_utc: datetime
    sst_activity_index: float
    rainfall_stress_index: float
    soil_saturation_index: float
    atmospheric_pressure_index: float
    oceanic_anomaly_index: float
    environmental_anomaly_index: float
    evidence_level: str = "C"

    def to_flat_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        data["reference_datetime_utc"] = format_datetime_utc(self.reference_datetime_utc)
        return data


class InternationalComparison(BaseModel):
    region_code: str
    reference_region: str
    similarity_score: float
    matching_features: list[str] = Field(default_factory=list)
    non_matching_features: list[str] = Field(default_factory=list)
    evidence_level: str = "C"
    scientific_notes: str = ""
