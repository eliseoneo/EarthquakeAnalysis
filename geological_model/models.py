"""Modelos de datos — FCN geoespacial geológico."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GeologicalInputFeatures(BaseModel):
    """Entradas alineadas con docs/foco-geologico.md (secciones 2.1–2.4)."""

    event_id: str
    source_document: str

    insar_displacement_cm: float | None = None
    insar_quality: str = "unknown"

    distance_to_fault_km: float | None = None
    estimated_slip_rate_mm_per_year: float | None = None
    nearby_geological_faults: list[str] = Field(default_factory=list)
    fault_count: int = 0

    vs30_m_per_s: float | None = None
    slope_degrees: float | None = None
    soil_moisture_index: float | None = None
    liquefaction_likelihood: str | None = None
    distance_to_coast_or_rivers_km: float | None = None
    landslide_susceptibility: str | None = None

    magnitude_mw: float | None = None
    gutenberg_richter_b_value: float | None = None

    def to_channel_vector(self) -> list[float]:
        """Vector de 4 canales (InSAR, tectónica, suelo, hidro-geotecnia)."""
        return [
            self._insar_channel(),
            self._tectonic_channel(),
            self._soil_channel(),
            self._hydro_geotech_channel(),
        ]

    def _insar_channel(self) -> float:
        if self.insar_displacement_cm is None:
            return 0.5
        return min(1.0, abs(self.insar_displacement_cm) / 20.0)

    def _tectonic_channel(self) -> float:
        if self.distance_to_fault_km is None:
            return 0.5
        proximity = max(0.0, 1.0 - (self.distance_to_fault_km / 100.0))
        slip = (self.estimated_slip_rate_mm_per_year or 0.0) / 15.0
        fault_density = min(1.0, self.fault_count / 4.0)
        return min(1.0, 0.45 * proximity + 0.35 * min(1.0, slip) + 0.20 * fault_density)

    def _soil_channel(self) -> float:
        if self.vs30_m_per_s is None:
            return 0.5
        if self.vs30_m_per_s < 180:
            return 0.92
        if self.vs30_m_per_s < 360:
            return 0.75
        if self.vs30_m_per_s < 760:
            return 0.45
        return 0.25

    def _hydro_geotech_channel(self) -> float:
        liquefaction = _likelihood_score(self.liquefaction_likelihood)
        landslide = _likelihood_score(self.landslide_susceptibility)
        moisture = self.soil_moisture_index if self.soil_moisture_index is not None else 0.5
        coastal = 0.0
        if self.distance_to_coast_or_rivers_km is not None:
            coastal = max(0.0, 1.0 - (self.distance_to_coast_or_rivers_km / 30.0))
        slope = min(1.0, (self.slope_degrees or 0.0) / 30.0)
        return min(
            1.0,
            0.35 * liquefaction
            + 0.25 * landslide
            + 0.20 * moisture
            + 0.10 * coastal
            + 0.10 * slope,
        )


class GeologicalModelOutput(BaseModel):
    """Salidas probabilísticas del FCN geoespacial geológico."""

    event_id: str
    model_type: str = "fcn_geoespacial_geologico"
    model_version: str = "1.0.0"
    source_document: str

    channel_scores: dict[str, float]
    geotechnical_vulnerability: float
    liquefaction_probability: float
    spatial_amplification_factor: float
    fault_coupling_index: float
    structural_damage_probability: float
    landslide_probability: float
    risk_category: str
    evidence_level: str = "B"
    modeling_notes: dict[str, Any] = Field(default_factory=dict)

    def to_flat_dict(self) -> dict[str, Any]:
        return self.model_dump()


def _likelihood_score(label: str | None) -> float:
    if not label:
        return 0.5
    normalized = label.strip().lower()
    mapping = {
        "baja": 0.2,
        "low": 0.2,
        "moderada": 0.55,
        "moderate": 0.55,
        "moderada en rellenos y aluviales": 0.6,
        "moderate-high": 0.7,
        "moderada-alta": 0.7,
        "alta": 0.85,
        "high": 0.85,
        "alta en laderas urbanas y periurbanas": 0.88,
        "high on slopes": 0.88,
        "critica": 0.95,
        "critical": 0.95,
    }
    for key, value in mapping.items():
        if key in normalized:
            return value
    return 0.5
