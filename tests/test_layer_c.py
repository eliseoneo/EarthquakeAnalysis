"""Tests unitarios — Capa C H04 analisis del evento."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from layer_c.paths import PROCESSED_DIR, REPORTS_DIR
from layer_c.pipeline import _fetch_funvisis_endpoint, _normalize_funvisis_dump, run_pipeline
from layer_a.ingestion.usgs_client import download_usgs_catalog


class TestPipeline:
    def test_run_pipeline_h04_event_analysis(self) -> None:
        summary = run_pipeline()

        assert summary["layer"] == "C_event_h04"
        assert summary["analysis_scope"] == "analisis del evento"
        assert summary["projection_mode"] is False
        assert summary["hypotheses_defined"] == 3
        assert summary["scientific_questions_defined"] == 7
        assert summary["catalog_sources_connected"] == 2
        assert summary["external_sources_cataloged"] >= 10
        assert summary["external_source_priority_rows"] >= 10
        assert summary["accelerography_records"] >= 1
        assert summary["geotechnical_records"] == 1
        assert summary["coverage_matrix_rows"] >= 5
        assert summary["funvisis_connector_status"] == "fallback_proxy"
        assert Path(PROCESSED_DIR / "h04_hypotheses.json").exists()
        assert Path(PROCESSED_DIR / "h04_catalog_source_coverage.json").exists()
        assert Path(PROCESSED_DIR / "h04_catalog_event_candidates.json").exists()
        assert Path(PROCESSED_DIR / "h04_source_coverage_matrix.json").exists()
        assert Path(PROCESSED_DIR / "h04_external_source_registry.json").exists()
        assert Path(PROCESSED_DIR / "h04_external_source_priorities.json").exists()
        assert Path(PROCESSED_DIR.parent / "raw" / "accelerography" / "accelerography_station_estimates.json").exists()
        assert Path(PROCESSED_DIR.parent / "raw" / "catalog_funvisis_fallback_proxy.json").exists()
        assert Path(PROCESSED_DIR.parent / "normalized" / "accelerography_station_records.json").exists()
        assert Path(PROCESSED_DIR.parent / "normalized" / "geotechnical_site_records.json").exists()
        assert Path(REPORTS_DIR / "h04_evidence_provenance.md").exists()
        assert Path(REPORTS_DIR / "h04_schema_reference.md").exists()
        assert Path(REPORTS_DIR / "h04_external_sources.md").exists()
        assert Path(REPORTS_DIR / "reporte_h04_evento_venezuela_2026.md").exists()

        coverage_rows = json.loads((PROCESSED_DIR / "h04_catalog_source_coverage.json").read_text(encoding="utf-8"))
        source_status = {row["source_name"]: row["availability_status"] for row in coverage_rows}
        assert source_status["USGS"] == "available_raw"
        assert source_status["FUNVISIS"] == "fixture_only"
        funvisis_row = next(row for row in coverage_rows if row["source_name"] == "FUNVISIS")
        assert "connector_status" in funvisis_row

        matrix_rows = json.loads((PROCESSED_DIR / "h04_source_coverage_matrix.json").read_text(encoding="utf-8"))
        assert any(row["source_name"] == "redes acelerograficas" for row in matrix_rows)
        assert any(row["source_name"] == "FUNVISIS" and row["availability_status"] == "fallback_proxy" for row in matrix_rows)

        accelerography_rows = json.loads((PROCESSED_DIR.parent / "normalized" / "accelerography_station_records.json").read_text(encoding="utf-8"))
        assert accelerography_rows[0]["measurement_mode"] == "instrumented_strong_motion"
        assert accelerography_rows[0]["provenance_reference"] == "local_raw_accelerography_fixture"

        external_registry_rows = json.loads((PROCESSED_DIR / "h04_external_source_registry.json").read_text(encoding="utf-8"))
        assert any(row["source_name"] == "USGS" and row["target_layer"] == "A_tectonic" for row in external_registry_rows)
        assert any(row["source_name"] == "ESM" and row["target_layer"] == "C_accelerography" for row in external_registry_rows)

        external_priority_rows = json.loads((PROCESSED_DIR / "h04_external_source_priorities.json").read_text(encoding="utf-8"))
        assert any(row["priority_tier"] == "level_1" and row["source_name"] == "FUNVISIS" for row in external_priority_rows)

        accelerography_schema = json.loads(
            (PROCESSED_DIR.parent.parent / "schemas" / "accelerography_record.schema.json").read_text(encoding="utf-8")
        )
        geotechnical_schema = json.loads(
            (PROCESSED_DIR.parent.parent / "schemas" / "geotechnical_site_record.schema.json").read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(accelerography_schema)
        Draft202012Validator.check_schema(geotechnical_schema)

        accelerography_raw = json.loads(
            (PROCESSED_DIR.parent / "raw" / "accelerography" / "accelerography_station_estimates.json").read_text(encoding="utf-8")
        )
        geotechnical_rows = json.loads(
            (PROCESSED_DIR.parent / "normalized" / "geotechnical_site_records.json").read_text(encoding="utf-8")
        )

        for record in accelerography_raw["records"]:
            Draft202012Validator(accelerography_schema).validate(record)
        for record in geotechnical_rows:
            Draft202012Validator(geotechnical_schema).validate(record)


class TestRawPreference:
    def test_pipeline_prefers_real_accelerography_raw_file(self) -> None:
        summary = run_pipeline()
        assert summary["accelerography_records"] >= 2

        matrix_rows = json.loads((PROCESSED_DIR / "h04_source_coverage_matrix.json").read_text(encoding="utf-8"))
        accelerography_rows = [row for row in matrix_rows if row["evidence_id"] == "EV-02"]
        assert accelerography_rows
        assert all(row["availability_status"] == "available_raw" for row in accelerography_rows)
        assert all(row["next_action"] == "integrado desde archivos raw por estacion" for row in accelerography_rows)


class TestFunvisisNormalization:
    def test_normalize_funvisis_feature_collection(self) -> None:
        payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Sismo",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-70.59, 10.06],
                    },
                    "properties": {
                        "depth": "9.0 km",
                        "value": "3.0",
                        "addressFormatted": "59 km al oeste de Carora",
                        "time": "09:06",
                        "country": "Venezuela",
                        "date": "26-09-2025",
                        "lat": "10.06",
                        "long": "-70.59",
                    },
                }
            ],
        }

        normalized = _normalize_funvisis_dump(payload)

        assert normalized["source"] == "funvisis"
        assert normalized["event_count"] == 1
        assert normalized["source_format"] == "feature_collection_recent_events"
        assert normalized["historical_scope"] == "recent_events_only"
        event = normalized["events"][0]
        assert event["source"] == "funvisis"
        assert event["datetime_utc"] == "2025-09-26 09:06:00"
        assert event["latitude"] == 10.06
        assert event["longitude"] == -70.59
        assert event["depth_km"] == 9.0
        assert event["magnitude"] == 3.0
        assert event["place"] == "59 km al oeste de Carora"


@pytest.mark.skipif(os.environ.get("EARTHQUAKEANALYSIS_LIVE_EXTERNAL", "0") != "1", reason="External-source integration disabled")
class TestExternalSourceLinks:
    def test_usgs_live_download_returns_real_events(self) -> None:
        from datetime import date

        events, status = download_usgs_catalog(
            start_date=date(2026, 6, 24),
            end_date=date(2026, 6, 25),
            min_magnitude=5.0,
            bbox={"min_lat": -5.0, "max_lat": 15.0, "min_lon": -85.0, "max_lon": -55.0},
            timeout_seconds=30,
        )
        assert events
        assert status.startswith("ok (")
        assert all("event_id" in event for event in events[:3])

    def test_funvisis_live_endpoint_returns_payload_when_configured(self) -> None:
        endpoint = os.environ.get("EARTHQUAKEANALYSIS_FUNVISIS_ENDPOINT", "").strip()
        if not endpoint:
            pytest.skip("FUNVISIS endpoint not configured")
        payload = _fetch_funvisis_endpoint(endpoint, timeout_seconds=20)
        assert payload is not None