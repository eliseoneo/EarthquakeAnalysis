"""FCN geoespacial geológico — proxy tabular sobre features implementadas."""

from __future__ import annotations

from typing import Any

import yaml

from geological_model.models import GeologicalInputFeatures, GeologicalModelOutput
from geological_model.paths import DEFAULT_CONFIG


class GeologicalFCNModel:
    """
    Fully Convolutional Network (FCN) geoespacial geológico.

    Implementación tabular que simula la agregación multicapa descrita en
    docs/foco-geologico.md usando canales InSAR, tectónica, suelo e hidro-geotecnia.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or self.load_config()

    @staticmethod
    def load_config(path: str | None = None) -> dict[str, Any]:
        config_path = DEFAULT_CONFIG if path is None else path
        with open(config_path, encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    def predict(self, features: GeologicalInputFeatures) -> GeologicalModelOutput:
        channels = features.to_channel_vector()
        channel_names = ["insar", "tectonic", "soil", "hydro_geotech"]
        channel_map = dict(zip(channel_names, channels, strict=True))

        weights = self.config["channel_weights"]
        weighted = sum(channels[i] * weights[name] for i, name in enumerate(channel_names))
        weighted = min(1.0, max(0.0, weighted))

        amplification = self._spatial_amplification(features.vs30_m_per_s)
        liquefaction = self._liquefaction_probability(features, channel_map)
        fault_coupling = min(1.0, 0.6 * channel_map["tectonic"] + 0.4 * channel_map["insar"])
        geotechnical = min(
            1.0,
            0.40 * weighted
            + 0.25 * liquefaction
            + 0.20 * (amplification - 0.7)
            + 0.15 * fault_coupling,
        )

        magnitude_factor = self._magnitude_factor(features.magnitude_mw)
        structural_damage = min(
            1.0,
            0.55 * geotechnical + 0.25 * amplification * 0.5 + 0.20 * magnitude_factor,
        )
        landslide = min(
            1.0,
            0.50 * channel_map["hydro_geotech"]
            + 0.30 * geotechnical
            + 0.20 * magnitude_factor,
        )

        return GeologicalModelOutput(
            event_id=features.event_id,
            source_document=features.source_document,
            channel_scores=channel_map,
            geotechnical_vulnerability=round(geotechnical, 4),
            liquefaction_probability=round(liquefaction, 4),
            spatial_amplification_factor=round(amplification, 4),
            fault_coupling_index=round(fault_coupling, 4),
            structural_damage_probability=round(structural_damage, 4),
            landslide_probability=round(landslide, 4),
            risk_category=self._risk_category(geotechnical),
            modeling_notes={
                "architecture": self.config.get("architecture", "FCN"),
                "reference_doc": "docs/foco-geologico.md",
                "loss_functions": self.config.get("loss_functions", []),
                "insar_available": features.insar_displacement_cm is not None,
                "insar_quality": features.insar_quality,
            },
        )

    def _spatial_amplification(self, vs30: float | None) -> float:
        if vs30 is None:
            return 1.0
        if vs30 < 180:
            return 1.85
        if vs30 < 360:
            return 1.45
        if vs30 < 760:
            return 1.05
        return 0.75

    def _liquefaction_probability(
        self,
        features: GeologicalInputFeatures,
        channels: dict[str, float],
    ) -> float:
        base = channels["hydro_geotech"]
        vs30_factor = 0.0
        if features.vs30_m_per_s is not None and features.vs30_m_per_s < 300:
            vs30_factor = min(1.0, (300.0 - features.vs30_m_per_s) / 200.0)
        moisture = features.soil_moisture_index or 0.5
        return min(1.0, 0.45 * base + 0.35 * vs30_factor + 0.20 * moisture)

    @staticmethod
    def _magnitude_factor(magnitude_mw: float | None) -> float:
        if magnitude_mw is None:
            return 0.5
        return min(1.0, max(0.0, (magnitude_mw - 4.0) / 4.0))

    @staticmethod
    def _risk_category(geotechnical: float) -> str:
        if geotechnical >= 0.82:
            return "riesgo_critico"
        if geotechnical >= 0.68:
            return "riesgo_alto"
        if geotechnical >= 0.45:
            return "riesgo_medio"
        return "riesgo_bajo"
