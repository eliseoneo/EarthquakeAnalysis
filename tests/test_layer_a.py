"""Tests unitarios — Capa A: Tectónica Principal."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from layer_a.formatting import format_datetime_utc, parse_datetime_utc

from layer_a.classifiers.depth import classify_depth
from layer_a.classifiers.focal_mechanism import classify_focal_mechanism
from layer_a.classifiers.magnitude import classify_magnitude
from layer_a.geo.distance import haversine_km
from layer_a.models import SeismicEvent
from layer_a.quality.deduplication import deduplicate_events
from layer_a.tectonic.aftershocks import detect_aftershocks
from layer_a.tectonic.b_value import calculate_b_value
from layer_a.tectonic.doublets import detect_doublets
from layer_a.tectonic.windows import build_temporal_windows


def _event(
    event_id: str,
    dt: str,
    lat: float,
    lon: float,
    mag: float,
    depth: float = 10.0,
    source: str = "usgs",
) -> SeismicEvent:
    return SeismicEvent(
        event_id=event_id,
        source=source,
        source_event_id=event_id,
        datetime_utc=parse_datetime_utc(dt),
        latitude=lat,
        longitude=lon,
        depth_km=depth,
        magnitude=mag,
        magnitude_type="Mw",
        magnitude_preferred=mag,
        magnitude_quality="high",
        depth_class=classify_depth(depth),
        magnitude_class=classify_magnitude(mag),
    )


class TestClassifiers:
    @pytest.mark.parametrize("mag,expected", [
        (2.5, "micro"), (3.5, "minor"), (4.5, "light"),
        (5.5, "moderate"), (6.5, "strong"), (7.5, "major"), (8.2, "great"),
    ])
    def test_classify_magnitude(self, mag: float, expected: str) -> None:
        assert classify_magnitude(mag) == expected

    @pytest.mark.parametrize("depth,expected", [
        (5, "shallow_critical"), (20, "shallow_crustal"),
        (50, "intermediate_shallow"), (150, "intermediate"), (400, "deep"),
    ])
    def test_classify_depth(self, depth: float, expected: str) -> None:
        assert classify_depth(depth) == expected

    @pytest.mark.parametrize("rake,expected", [
        (None, "unknown"), (0, "strike_slip"), (-90, "normal"),
        (90, "reverse_thrust"), (45, "oblique"),
    ])
    def test_classify_focal_mechanism(self, rake: float | None, expected: str) -> None:
        assert classify_focal_mechanism(rake) == expected


class TestDistance:
    def test_haversine_zero(self) -> None:
        assert haversine_km(10.0, -62.0, 10.0, -62.0) == 0.0

    def test_haversine_positive(self) -> None:
        dist = haversine_km(10.0, -62.0, 10.5, -62.5)
        assert 50 < dist < 90


class TestDeduplication:
    def test_merge_duplicate_events(self) -> None:
        a = _event("a", "2026-06-24T12:00:00Z", 10.52, -62.78, 7.2, source="usgs")
        b = _event("b", "2026-06-24T12:00:30Z", 10.51, -62.79, 7.5, source="funvisis")
        cfg = {
            "time_tolerance_seconds": 120,
            "distance_tolerance_km": 50,
            "magnitude_tolerance": 0.3,
            "depth_tolerance_km": 25,
        }
        result = deduplicate_events([a, b], cfg, ["usgs", "funvisis"])
        assert len(result) == 1
        assert result[0].source_count == 2
        assert result[0].has_conflict


class TestAftershocks:
    def test_detect_aftershocks(self) -> None:
        main = _event("main", "2026-06-24T12:00:00Z", 10.52, -62.78, 7.2)
        as1 = _event("as1", "2026-06-24T18:00:00Z", 10.50, -62.80, 5.5)
        as2 = _event("as2", "2026-07-01T12:00:00Z", 10.48, -62.85, 4.8)
        unrelated = _event("far", "2026-06-25T12:00:00Z", 5.0, -75.0, 5.0)
        tagged, seq = detect_aftershocks(main, [main, as1, as2, unrelated])
        assert len(tagged) == 2
        assert seq.aftershock_count_7d >= 2


class TestDoublets:
    def test_detect_doublet_candidates(self) -> None:
        e1 = _event("e1", "2026-06-24T12:00:00Z", 10.52, -62.78, 7.2)
        e2 = _event("e2", "2026-06-24T13:00:00Z", 10.55, -62.70, 7.0)
        cfg = {
            "min_magnitude": 6.0,
            "max_time_delta_hours": 24,
            "strict_time_delta_hours": 1,
            "max_distance_km": 250,
            "strict_distance_km": 100,
            "max_magnitude_delta": 0.5,
            "strict_magnitude_delta": 0.3,
        }
        candidates = detect_doublets([e1, e2], cfg)
        assert len(candidates) >= 1
        assert candidates[0].classification in {"possible_doublet", "high_confidence_doublet"}


class TestBValue:
    def test_b_value_insufficient_sample(self) -> None:
        events = [_event(f"e{i}", "2026-01-01T00:00:00Z", 10.0, -62.0, 3.0 + i * 0.1) for i in range(5)]
        result = calculate_b_value(events)
        assert result.b_value is None
        assert result.confidence_level == "D"

    def test_b_value_with_sample(self) -> None:
        events = [_event(f"e{i}", "2026-01-01T00:00:00Z", 10.0, -62.0, 3.0 + (i % 20) * 0.1) for i in range(60)]
        result = calculate_b_value(events)
        assert result.b_value is not None
        assert result.confidence_level == "A"


class TestTemporalWindows:
    def test_build_windows(self) -> None:
        main = _event("main", "2026-06-24T12:00:00Z", 10.52, -62.78, 7.2)
        before = _event("before", "2026-06-10T12:00:00Z", 10.60, -62.65, 4.5)
        after = _event("after", "2026-06-25T12:00:00Z", 10.50, -62.80, 5.5)
        rows = build_temporal_windows(main, [main, before, after], [-30, 0, 7])
        assert len(rows) == 3
        assert rows[0]["event_count"] >= 1
        assert rows[2]["event_count"] >= 1


class TestFormatting:
    def test_format_datetime_utc(self) -> None:
        dt = parse_datetime_utc("2026-06-24 12:00:00")
        assert format_datetime_utc(dt) == "2026-06-24 12:00:00"

    def test_parse_iso_legacy(self) -> None:
        dt = parse_datetime_utc("2026-06-24T12:00:00Z")
        assert format_datetime_utc(dt) == "2026-06-24 12:00:00"

    def test_to_flat_dict_uses_standard_format(self) -> None:
        event = _event("e1", "2026-06-24 12:00:00", 10.0, -62.0, 5.0)
        assert event.to_flat_dict()["datetime_utc"] == "2026-06-24 12:00:00"


class TestUsgsClient:
    def test_feature_to_event(self) -> None:
        from layer_a.ingestion.usgs_client import _feature_to_event

        feature = {
            "properties": {
                "mag": 7.2,
                "magType": "mww",
                "place": "Test",
                "time": 1782302400000,
                "ids": "us6000test,at00test",
                "status": "reviewed",
            },
            "geometry": {"coordinates": [-62.78, 10.52, 10.0]},
        }
        event = _feature_to_event(feature)
        assert event is not None
        assert event["magnitude"] == 7.2
        assert event["source_event_id"] == "us6000test"
        assert event["event_id"] == "us6000test"
