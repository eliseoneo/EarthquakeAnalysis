"""Tests unitarios — Capa B Geofísica Ambiental."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from layer_b.analytics.correlation import compute_correlation, mann_whitney_test
from layer_b.analytics.temporal import cross_correlation, rolling_correlation
from layer_b.comparison.international import compare_regions
from layer_b.features.engineering import build_sst_features
from layer_b.formatting import format_datetime_utc, parse_datetime_utc
from layer_b.indices.environmental_indexes import compute_environmental_indexes
from layer_b.ingestion.synthetic import generate_connector_observations
from layer_b.models import EnvironmentalObservation, FeatureRecord
from layer_b.normalization.timeseries_normalizer import normalize_observation
from layer_b.pipeline import run_pipeline


def _obs(region: str, day: str, domain: str, variable: str, value: float) -> EnvironmentalObservation:
    return EnvironmentalObservation(
        observation_id=f"{region}_{variable}_{day}",
        region_code=region,
        datetime_utc=parse_datetime_utc(f"{day} 12:00:00"),
        domain=domain,
        variable=variable,
        value=value,
        unit="",
        source="test",
    )


class TestFormatting:
    def test_datetime_format(self) -> None:
        dt = parse_datetime_utc("2026-06-24 12:00:00")
        assert format_datetime_utc(dt) == "2026-06-24 12:00:00"


class TestSynthetic:
    def test_generate_sst_rows(self) -> None:
        from datetime import date
        rows = generate_connector_observations(
            "sst", ["venezuela"], date(2026, 6, 1), date(2026, 6, 10)
        )
        assert len(rows) == 10
        assert rows[0]["domain"] == "oceanic"


class TestFeatures:
    def test_sst_features(self) -> None:
        observations = [
            _obs("venezuela", f"2026-06-{d:02d}", "oceanic", "sst", 27.0 + d * 0.1)
            for d in range(1, 31)
        ]
        ref = parse_datetime_utc("2026-06-24 12:00:00")
        feats = build_sst_features(observations, "venezuela", ref)
        names = {f.feature_name for f in feats}
        assert "sst_mean_7d" in names
        assert "sst_anomaly" in names


class TestAnalytics:
    def test_pearson_correlation(self) -> None:
        x = list(range(10))
        y = [v * 2 for v in x]
        result = compute_correlation("venezuela", "x", x, "y", y, "pearson")
        assert result.coefficient is not None
        assert result.coefficient > 0.9

    def test_mann_whitney(self) -> None:
        result = mann_whitney_test([1, 2, 3, 4], [5, 6, 7, 8])
        assert result["p_value"] is not None

    def test_cross_correlation(self) -> None:
        x = [float(i) for i in range(20)]
        y = [float(i) for i in range(20)]
        result = cross_correlation(x, y)
        assert result["best_coef"] is not None


class TestIndexes:
    def test_environmental_indexes_range(self) -> None:
        ref = parse_datetime_utc("2026-06-24 12:00:00")
        feats = [
            FeatureRecord(
                region_code="venezuela",
                reference_datetime_utc=ref,
                feature_name="sst_anomaly",
                feature_value=1.0,
            ),
            FeatureRecord(
                region_code="venezuela",
                reference_datetime_utc=ref,
                feature_name="rain_acc_7d",
                feature_value=50.0,
            ),
        ]
        idx = compute_environmental_indexes("venezuela", ref, feats)
        assert 0 <= idx.environmental_anomaly_index <= 100


class TestInternational:
    def test_compare_regions(self) -> None:
        maps = {
            "venezuela": {"sst_mean_7d": 28.0, "rain_acc_7d": 40.0},
            "colombia": {"sst_mean_7d": 27.5, "rain_acc_7d": 45.0},
        }
        rows = compare_regions("venezuela", maps, ["sst_mean_7d", "rain_acc_7d"])
        assert len(rows) == 1
        assert 0 <= rows[0].similarity_score <= 1


class TestPipeline:
    def test_run_pipeline_synthetic(self) -> None:
        summary = run_pipeline(use_synthetic=True)
        assert summary["layer"] == "B_geophysical"
        assert summary["observations_normalized"] > 0
        assert summary["features_computed"] > 0
