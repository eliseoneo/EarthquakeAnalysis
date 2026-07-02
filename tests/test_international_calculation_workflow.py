from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from international_calculation_workflow import (  # noqa: E402
    FEATURE_ORDER,
    SeismicSample,
    _enrich_trend_features,
    _gr_exceedance_probability,
    _gr_tail_mmax_forecast,
    _walk_forward_split_indices,
    build_window_dataset,
    run_international_estimation,
)


def _synthetic_events() -> list[SeismicSample]:
    sources = [
        ("usgs", "USA"),
        ("ingv", "Italia"),
        ("sgc", "Colombia"),
    ]
    events: list[SeismicSample] = []
    base = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    for idx in range(180):
        source, country = sources[idx % 3]
        dt = base + timedelta(days=idx * 2)
        magnitude = 3.8 + (idx % 7) * 0.22
        events.append(
            SeismicSample(
                event_id=f"{source}_{idx}",
                source=source,
                country=country,
                dt_utc=dt,
                latitude=10.0 + (idx % 8),
                longitude=-70.0 + (idx % 9),
                magnitude=magnitude,
            )
        )
    return events


def test_build_window_dataset_generates_expected_features():
    as_of = date(2026, 1, 15)
    dataset = build_window_dataset(
        events=_synthetic_events(),
        as_of_date=as_of,
        lookback_days=300,
        window_days=45,
        stride_days=10,
        horizon_days=20,
        threshold_magnitude=5.0,
    )
    assert len(dataset) >= 8
    first = dataset[0]
    for feature in FEATURE_ORDER:
        assert feature in first.features


def test_run_international_estimation_with_custom_model_options(monkeypatch, tmp_path: Path):
    events = _synthetic_events()
    source_table = [
        ["USGS", "USA", "synthetic", 60, "2025-01-01", "2025-12-31"],
        ["INGV", "Italia", "synthetic", 60, "2025-01-01", "2025-12-31"],
        ["SGC", "Colombia", "synthetic", 60, "2025-01-01", "2025-12-31"],
    ]

    def _fake_loader(*args, **kwargs):
        return events, source_table

    def _fake_save(payload, as_of_date):
        out_path = tmp_path / "international_estimation_test.json"
        out_path.write_text("{}", encoding="utf-8")
        return out_path

    monkeypatch.setattr(
        "international_calculation_workflow.load_international_events",
        _fake_loader,
    )
    monkeypatch.setattr(
        "international_calculation_workflow._save_run",
        _fake_save,
    )

    payload = run_international_estimation(
        as_of_date=date(2026, 1, 15),
        lookback_days=320,
        window_days=60,
        stride_days=12,
        horizon_days=25,
        threshold_magnitude=5.0,
        alternative_threshold_magnitude=4.0,
        min_magnitude=3.0,
        use_live_sources=False,
        walk_forward_min_train=6,
        walk_forward_test_size=2,
        walk_forward_step=2,
        use_platt_calibration=False,
        use_class_weight=True,
    )

    assert payload["status"] == "ok"
    assert payload["parameters"]["alternative_threshold_magnitude"] == 4.0
    assert payload["parameters"]["probability_calibration"] == "none"
    assert payload["parameters"]["walk_forward_min_train"] == 6


def test_run_international_estimation_with_synthetic_loader(monkeypatch, tmp_path: Path):
    events = _synthetic_events()
    source_table = [
        ["USGS", "USA", "synthetic", 60, "2025-01-01", "2025-12-31"],
        ["INGV", "Italia", "synthetic", 60, "2025-01-01", "2025-12-31"],
        ["SGC", "Colombia", "synthetic", 60, "2025-01-01", "2025-12-31"],
    ]

    def _fake_loader(*args, **kwargs):
        return events, source_table

    def _fake_save(payload, as_of_date):
        out_path = tmp_path / "international_estimation_test.json"
        out_path.write_text("{}", encoding="utf-8")
        return out_path

    monkeypatch.setattr(
        "international_calculation_workflow.load_international_events",
        _fake_loader,
    )
    monkeypatch.setattr(
        "international_calculation_workflow._save_run",
        _fake_save,
    )

    payload = run_international_estimation(
        as_of_date=date(2026, 1, 15),
        lookback_days=320,
        window_days=60,
        stride_days=12,
        horizon_days=25,
        threshold_magnitude=5.0,
        min_magnitude=3.0,
        use_live_sources=False,
    )

    assert payload["status"] == "ok"
    assert payload["source_table"]
    assert payload["feature_rows"]
    assert payload["insar_gnss_rows"]
    assert payload["prediction_rows"]
    assert payload["metrics_rows"]
    assert payload["similarity_rows"]
    assert payload["anomaly_reference_window"] != "-"
    assert payload["importance_rows"]
    assert payload["ablation_rows"]
    first_insar = payload["insar_gnss_rows"][0]
    assert first_insar[5] == "proxy_from_seismic_catalog"
    assert first_insar[2] is not None
    assert payload["geological_insar_bridge"]["status"] == "connected"
    assert payload["walk_forward_metrics"]["classification_m5"]
    assert payload["walk_forward_metrics"]["classification_m45"]


def test_enrich_trend_features_adds_new_columns():
    events = _synthetic_events()[:20]
    base = {
        "n_events": 20.0,
        "m_mean": 4.2,
        "gr_b": 1.0,
        "gr_a": 3.0,
        "benioff_rate": 100.0,
        "delta_m": 0.1,
        "mu_recurrence_days": 5.0,
        "eta_rms": 0.1,
        "n_usgs": 20.0,
        "n_ingv": 0.0,
        "n_sgc": 0.0,
        "max_magnitude_in_window": 5.0,
        "benioff_accel": 0.0,
        "gr_b_delta": 0.0,
        "event_rate_trend": 0.0,
    }
    enriched = _enrich_trend_features(base, events, window_days=90, prev_benioff=80.0)
    assert enriched["max_magnitude_in_window"] == 5.0
    assert "benioff_accel" in enriched
    assert "gr_b_delta" in enriched
    assert "event_rate_trend" in enriched


def test_gr_tail_helpers_return_bounded_values():
    exceedance = _gr_exceedance_probability(3.0, 1.0, rate_per_day=0.2, horizon_days=30, threshold=5.0)
    mmax = _gr_tail_mmax_forecast(3.0, 1.0, rate_per_day=0.2, horizon_days=30)
    assert 0.0 <= exceedance <= 1.0
    assert 0.0 <= mmax <= 9.5


def test_walk_forward_split_indices_cover_tail():
    splits = _walk_forward_split_indices(20, min_train=8, test_size=3, step=3)
    assert splits
    assert splits[-1][1] <= 20


def test_build_window_dataset_includes_alternative_label():
    as_of = date(2026, 1, 15)
    dataset = build_window_dataset(
        events=_synthetic_events(),
        as_of_date=as_of,
        lookback_days=300,
        window_days=45,
        stride_days=10,
        horizon_days=20,
        threshold_magnitude=5.0,
    )
    assert dataset
    assert hasattr(dataset[0], "target_probability_label_m45")
    assert hasattr(dataset[0], "target_exceedance_prob")
    assert 0.0 <= dataset[0].target_exceedance_prob <= 1.0
    assert dataset[0].features["max_magnitude_in_window"] >= 0.0
