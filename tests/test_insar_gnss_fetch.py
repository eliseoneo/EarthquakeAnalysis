"""Tests — obtención y reemplazo InSAR/GNSS medidos."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from geological_model.insar_bridge import STATUS_MEASURED, STATUS_PROXY
from geological_model.insar_gnss_fetch import (
    apply_insar_replacement_to_payload,
    build_measured_rows_from_stations,
    parse_midas_velocity_line,
    persist_international_payload,
    replace_insar_gnss_rows,
    window_stubs_from_rows,
)


FIXTURE = Path("tests/fixtures/geological/ngl_midas_igs14.txt")


class _Sample:
    def __init__(self, start: date, end: date) -> None:
        self.start_date = start
        self.end_date = end
        self.features = {"benioff_rate": 1.0, "delta_m": 0.2, "m_mean": 4.0}


class TestMidasParser:
    def test_parse_station_line(self) -> None:
        line = FIXTURE.read_text(encoding="utf-8").splitlines()[0]
        station = parse_midas_velocity_line(line)
        assert station is not None
        assert station.station_id == "ACDZ"
        assert station.vsr_mm_per_year > 0
        assert station.ssr_mm_per_year > 0


class TestMeasuredReplacement:
    def test_replace_proxy_with_measured(self) -> None:
        proxy_rows = [
            ["2026-05-13", "2026-05-27", 1.0, 1.0, 1.0, STATUS_PROXY, "proxy"],
        ]
        measured_rows = [
            ["2026-05-13", "2026-05-27", 8.7, 15.5, 17.8, STATUS_MEASURED, "measured"],
        ]
        replaced, meta = replace_insar_gnss_rows(proxy_rows, measured_rows)
        assert replaced[0][5] == STATUS_MEASURED
        assert meta["rows_replaced"] == 1

    def test_build_measured_rows_from_fixture_stations(self) -> None:
        stations = []
        for line in FIXTURE.read_text(encoding="utf-8").splitlines():
            parsed = parse_midas_velocity_line(line)
            if parsed is not None:
                stations.append(parsed)
        samples = [_Sample(date(2022, 6, 1), date(2024, 6, 1))]
        measured_rows = build_measured_rows_from_stations(samples, stations)
        assert measured_rows
        assert measured_rows[0][5] == STATUS_MEASURED

    def test_window_stubs_from_rows(self) -> None:
        stubs = window_stubs_from_rows([["2026-01-01", "2026-01-31", None, None, None, STATUS_PROXY, ""]])
        assert len(stubs) == 1
        assert stubs[0].start_date == date(2026, 1, 1)


class TestInternationalPayloadUpdate:
    def test_apply_and_persist_international_payload(self, tmp_path: Path) -> None:
        payload = {
            "as_of_date": "2026-07-01",
            "insar_gnss_rows": [
                ["2026-05-13", "2026-05-27", 1.0, 1.0, 1.0, STATUS_PROXY, "proxy"],
            ],
        }
        measured_rows = [
            ["2026-05-13", "2026-05-27", 8.7, 15.5, 17.8, STATUS_MEASURED, "measured"],
        ]
        replaced, replace_meta = replace_insar_gnss_rows(payload["insar_gnss_rows"], measured_rows)
        updated = apply_insar_replacement_to_payload(payload, replaced, replace_meta)
        out_path = persist_international_payload(tmp_path / "international_estimation_test.json", updated)

        saved = json.loads(out_path.read_text(encoding="utf-8"))
        assert saved["insar_gnss_rows"][0][5] == STATUS_MEASURED
        assert saved["insar_gnss_placeholder_policy"]["status"] == STATUS_MEASURED
        assert saved["geological_insar_bridge"]["latest_data_status"] == STATUS_MEASURED
        assert "insar_updated_at_utc" in saved
