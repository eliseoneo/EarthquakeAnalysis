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
    assert first_insar[5] == "placeholder_pending_source"
