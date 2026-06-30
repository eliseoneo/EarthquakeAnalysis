from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from projection_model import (  # noqa: E402
    build_calibrated_forward_projection_row,
    build_forward_projection_row,
    build_hindcast_certainty_rows,
    calibrate_from_hindcast,
    cum_omori,
    probability_m_ge,
    PROJECTION_SCENARIOS,
)
from validation import load_yaml, discover_files  # noqa: E402


@pytest.fixture
def venezuela_2026_case() -> dict:
    return load_yaml(ROOT / "case_library/venezuela_2026/event.yaml")


def test_cum_omori_p_equals_one():
    K = 37.8569
    assert cum_omori(8, K, 1.0) == pytest.approx(83.18, rel=1e-3)


def test_forward_projection_venezuela_base(venezuela_2026_case):
    row = build_forward_projection_row(
        case_id="venezuela_2026",
        seismic=venezuela_2026_case["advanced_features"]["seismic"],
        similarity=venezuela_2026_case["similar_magnitude_probability_dates"],
        as_of_date=date(2026, 6, 29),
        forward_days=8,
        magnitude_target_mw=6.0,
        scenario_key="base",
    )
    assert row is not None
    assert row.elapsed_days_from_main == 5
    assert row.horizon_days_from_main == 13
    assert row.additional_expected_aftershocks == pytest.approx(32.08, rel=1e-2)
    assert row.probability_m_ge_target == pytest.approx(0.3985, rel=1e-3)
    assert row.observed_max_magnitude_mw == pytest.approx(4.5)


def test_scenario_ordering_conservative_below_optimistic(venezuela_2026_case):
    kwargs = {
        "case_id": "venezuela_2026",
        "seismic": venezuela_2026_case["advanced_features"]["seismic"],
        "similarity": venezuela_2026_case["similar_magnitude_probability_dates"],
        "as_of_date": date(2026, 6, 29),
        "forward_days": 8,
        "magnitude_target_mw": 6.0,
    }
    conservative = build_forward_projection_row(**kwargs, scenario_key="conservador")
    base = build_forward_projection_row(**kwargs, scenario_key="base")
    optimistic = build_forward_projection_row(**kwargs, scenario_key="optimista")
    assert conservative is not None and base is not None and optimistic is not None
    assert conservative.probability_m_ge_target < base.probability_m_ge_target
    assert base.probability_m_ge_target < optimistic.probability_m_ge_target


def test_projection_scenarios_have_expected_keys():
    for key in ("base", "conservador", "optimista"):
        assert key in PROJECTION_SCENARIOS


def test_probability_monotonic_with_n_additional():
    low = probability_m_ge(10.0, 6.0, 0.9)
    high = probability_m_ge(40.0, 6.0, 0.9)
    assert low < high


def test_hindcast_includes_venezuela_reference_index(venezuela_2026_case):
    rows = build_hindcast_certainty_rows(
        case_ids=["venezuela_2026"],
        case_lookup={"venezuela_2026": venezuela_2026_case},
        validation_days=8,
        magnitude_target_mw=6.0,
        scenario_key="base",
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.certainty_delta_vs_venezuela_2026 == pytest.approx(0.0)
    assert row.certainty_vs_venezuela_2026_percent == pytest.approx(100.0)


def test_calibrate_from_hindcast_excludes_venezuela(venezuela_2026_case):
    case_lookup: dict = {"venezuela_2026": venezuela_2026_case}
    for path in discover_files(["case_library/**/event.yaml"], ROOT):
        doc = load_yaml(path)
        case_lookup[str(doc.get("case_id", path.parent.name))] = doc

    calibration = calibrate_from_hindcast(
        list(case_lookup.keys()),
        case_lookup,
        validation_days=8,
        magnitude_target_mw=6.0,
    )
    assert calibration is not None
    assert "venezuela_2026" not in calibration.training_case_ids
    assert calibration.k_factor > 0

    calibrated_row = build_calibrated_forward_projection_row(
        case_lookup,
        calibration,
        date(2026, 6, 29),
        forward_days=8,
        magnitude_target_mw=6.0,
    )
    assert calibrated_row is not None
    assert calibrated_row.case_id == "venezuela_2026"
    assert calibrated_row.scenario == "calibrado"
