import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from validation import load_json, validate_against_schema


def test_event_case_synthetic_fixture_matches_schema():
    schema = load_json(ROOT / "schemas" / "event_case.schema.json")
    fixture = load_json(
        ROOT / "tests" / "fixtures" / "synthetic" / "venezuela_2026_june_minimal.json"
    )
    errors = validate_against_schema(fixture, schema)
    assert not errors, errors


def test_comparable_event_synthetic_fixture_matches_schema():
    schema = load_json(ROOT / "schemas" / "comparable_event.schema.json")
    fixture = load_json(
        ROOT / "tests" / "fixtures" / "synthetic" / "comparable_event_minimal.json"
    )
    errors = validate_against_schema(fixture, schema)
    assert not errors, errors
