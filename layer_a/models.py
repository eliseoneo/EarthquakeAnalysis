"""Modelos Pydantic para eventos sísmicos — Capa A."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from layer_a.formatting import format_datetime_utc


class CompatBaseModel(BaseModel):
    """Pydantic v1/v2 compatibility shim used across Layer A models."""

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        base = super()
        if hasattr(base, "model_dump"):
            return base.model_dump(*args, **kwargs)
        return self.dict(*args, **kwargs)

    def model_copy(self, *args: Any, **kwargs: Any) -> Any:
        base = super()
        if hasattr(base, "model_copy"):
            return base.model_copy(*args, **kwargs)
        return self.copy(*args, **kwargs)


class SeismicEvent(CompatBaseModel):
    event_id: str
    source: str
    source_event_id: str
    datetime_utc: datetime
    latitude: float
    longitude: float
    depth_km: float
    magnitude: float
    magnitude_type: str
    place: str = ""
    status: str = "reviewed"
    location_uncertainty_km: float | None = None
    depth_uncertainty_km: float | None = None
    magnitude_uncertainty: float | None = None

    magnitude_preferred: float | None = None
    magnitude_quality: str = "unknown"

    region_code: str | None = None
    tectonic_zone: str | None = None
    nearest_fault_name: str | None = None
    distance_to_nearest_fault_km: float | None = None
    nearest_plate_boundary: str | None = None
    distance_to_plate_boundary_km: float | None = None
    fault_system: str | None = None
    fault_type: str | None = None
    plate_context: str | None = None

    depth_class: str | None = None
    magnitude_class: str | None = None
    is_mainshock: bool = False
    is_aftershock: bool = False
    is_foreshock: bool = False
    is_doublet_candidate: bool = False
    is_multiplet_candidate: bool = False
    sequence_id: str | None = None
    confidence_level: str = "C"

    strike: float | None = None
    dip: float | None = None
    rake: float | None = None
    nodal_plane_1: str | None = None
    nodal_plane_2: str | None = None
    moment_tensor_available: bool = False
    focal_mechanism_type: str | None = None

    b_value_window: float | None = None
    aftershock_count_3d: int | None = None
    aftershock_count_7d: int | None = None
    aftershock_count_30d: int | None = None
    aftershock_rate_index: str | None = None
    tectonic_activity_index: str | None = None
    fault_proximity_index: str | None = None
    depth_risk_index: str | None = None
    magnitude_energy_index: str | None = None

    merged_source_ids: list[str] = Field(default_factory=list)
    source_count: int = 1
    has_conflict: bool = False
    conflict_fields: list[str] = Field(default_factory=list)
    population_exposure_placeholder: float | None = None

    def to_flat_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        data["datetime_utc"] = format_datetime_utc(self.datetime_utc)
        return data


class DoubletCandidate(CompatBaseModel):
    doublet_id: str
    event_id_1: str
    event_id_2: str
    time_delta_seconds: float
    distance_km: float
    magnitude_delta: float
    depth_delta_km: float
    same_fault_system: bool = False
    same_focal_mechanism_type: bool = False
    confidence_level: str
    classification: str


class AftershockSequence(CompatBaseModel):
    mainshock_id: str
    aftershock_ids: list[str]
    aftershock_count_3d: int
    aftershock_count_7d: int
    aftershock_count_30d: int
    aftershock_count_90d: int
    aftershock_count_365d: int
    max_aftershock_magnitude: float | None
    mean_aftershock_depth: float | None
    spatial_dispersion_km: float | None


class TectonicIndexRecord(CompatBaseModel):
    event_id: str
    tectonic_activity_index: str
    fault_proximity_index: str
    aftershock_rate_index: str
    depth_risk_index: str
    magnitude_energy_index: str
    evidence_level: str = "C"
