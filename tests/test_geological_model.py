"""Tests — modelo FCN geoespacial geológico."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from geological_model.extractors import extract_from_event_document
from geological_model.fcn_model import GeologicalFCNModel
from geological_model.insar_bridge import (
    STATUS_PROXY,
    build_insar_gnss_rows,
    parse_insar_gnss_rows,
    resolve_insar_from_event_document,
    select_insar_for_event_window,
)
from geological_model.losses import (
    fault_distance_epicenter_weights,
    gutenberg_richter_magnitude_weights,
    stpidn_combined_weights,
    weighted_mse_mae,
)
from geological_model.models import GeologicalInputFeatures
from geological_model.pipeline import run_pipeline


FIXTURE = Path("tests/fixtures/synthetic/venezuela_2026_june_minimal.json")
INTERNATIONAL_FIXTURE = Path(
    "storage/venezuela/international/2026/07/01/international_estimation_20260701T044446Z.json"
)


class _Sample:
    def __init__(self, start: date, end: date, features: dict[str, float]) -> None:
        self.start_date = start
        self.end_date = end
        self.features = features


class TestGeologicalInputFeatures:
    def test_channel_vector_shape(self) -> None:
        features = GeologicalInputFeatures(
            event_id="test",
            source_document="unit",
            vs30_m_per_s=290.0,
            distance_to_fault_km=16.0,
            estimated_slip_rate_mm_per_year=7.0,
            fault_count=3,
            liquefaction_likelihood="Moderate-high",
        )
        channels = features.to_channel_vector()
        assert len(channels) == 4
        assert all(0.0 <= value <= 1.0 for value in channels)


class TestInsarBridge:
    def test_build_proxy_rows(self) -> None:
        rows = build_insar_gnss_rows(
            [
                _Sample(
                    date(2026, 5, 13),
                    date(2026, 5, 27),
                    {"benioff_rate": 2.5, "delta_m": 0.8, "m_mean": 4.2},
                )
            ]
        )
        assert rows[0][5] == STATUS_PROXY
        assert rows[0][2] is not None

    def test_resolve_insar_for_event_fixture(self) -> None:
        if not INTERNATIONAL_FIXTURE.exists():
            return
        event_data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload = json.loads(INTERNATIONAL_FIXTURE.read_text(encoding="utf-8"))
        displacement, quality, meta = resolve_insar_from_event_document(event_data, payload)
        assert meta["connected"] is True
        if displacement is not None:
            assert quality == "proxy_seismic_catalog"

    def test_select_window_overlap(self) -> None:
        observations = parse_insar_gnss_rows(
            [
                ["2026-05-13", "2026-05-27", 1.0, 1.0, 1.0, STATUS_PROXY, "x"],
                ["2026-03-14", "2026-03-28", 0.5, 0.5, 0.5, STATUS_PROXY, "y"],
            ]
        )
        selected = select_insar_for_event_window(
            observations,
            date(2026, 6, 24),
            date(2026, 6, 26),
        )
        assert selected is not None
        assert selected.window_start == date(2026, 5, 13)


class TestGeologicalFCNModel:
    def test_predict_from_fixture(self) -> None:
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        features = extract_from_event_document(data, source_document=str(FIXTURE))
        model = GeologicalFCNModel()
        output = model.predict(features)

        assert output.model_type == "fcn_geoespacial_geologico"
        assert 0.0 <= output.geotechnical_vulnerability <= 1.0
        assert 0.0 <= output.liquefaction_probability <= 1.0
        assert output.risk_category.startswith("riesgo_")
        assert set(output.channel_scores) == {"insar", "tectonic", "soil", "hydro_geotech"}

    def test_insar_channel_changes_score(self) -> None:
        base = GeologicalInputFeatures(
            event_id="a",
            source_document="unit",
            vs30_m_per_s=250.0,
            distance_to_fault_km=10.0,
            estimated_slip_rate_mm_per_year=8.0,
            fault_count=2,
            liquefaction_likelihood="Alta",
        )
        with_insar = base.model_copy(update={"insar_displacement_cm": 18.0})
        model = GeologicalFCNModel()
        base_out = model.predict(base)
        insar_out = model.predict(with_insar)
        assert insar_out.fault_coupling_index >= base_out.fault_coupling_index


class TestLossFunctions:
    def test_weighted_mse_mae(self) -> None:
        loss = weighted_mse_mae([1.0, 0.0], [0.5, 0.0], [2.0, 1.0])
        assert loss > 0.0

    def test_stpidn_weights(self) -> None:
        mag_w = gutenberg_richter_magnitude_weights([4.0, 6.5], b_value=1.0)
        dist_w = fault_distance_epicenter_weights([80.0, 10.0])
        combined = stpidn_combined_weights([4.0, 6.5], [80.0, 10.0])
        assert mag_w[1] > mag_w[0]
        assert dist_w[1] > dist_w[0]
        assert len(combined) == 2


class TestPipeline:
    def test_run_pipeline_on_fixtures(self) -> None:
        summary = run_pipeline(
            patterns=["tests/fixtures/synthetic/*minimal.json"],
            output_dir=Path("storage/geological_model/outputs/test_run"),
            use_latest_international=INTERNATIONAL_FIXTURE.exists(),
        )
        assert summary["cases_evaluated"] >= 2
        assert Path(summary["output"]).exists()
