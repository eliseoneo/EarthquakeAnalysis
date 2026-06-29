import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_required_fields(schema: dict, data: dict) -> None:
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    for field in required:
        assert field in data, f"Missing required field: {field}"

    for field, definition in properties.items():
        if field not in data:
            continue

        if definition.get("type") == "object":
            nested_data = data[field]
            assert isinstance(nested_data, dict), f"Field {field} must be object"
            _validate_required_fields(definition, nested_data)

        if definition.get("type") == "array" and "items" in definition:
            assert isinstance(data[field], list), f"Field {field} must be array"
            item_schema = definition["items"]
            if item_schema.get("type") == "object":
                for item in data[field]:
                    assert isinstance(item, dict), f"Array item in {field} must be object"
                    _validate_required_fields(item_schema, item)


def test_event_case_synthetic_fixture_matches_schema():
    schema = _load_json(ROOT / "schemas" / "event_case.schema.json")
    fixture = _load_json(
        ROOT / "tests" / "fixtures" / "synthetic" / "venezuela_2026_june_minimal.json"
    )
    _validate_required_fields(schema, fixture)


def test_comparable_event_synthetic_fixture_matches_schema():
    schema = _load_json(ROOT / "schemas" / "comparable_event.schema.json")
    fixture = _load_json(
        ROOT / "tests" / "fixtures" / "synthetic" / "comparable_event_minimal.json"
    )
    _validate_required_fields(schema, fixture)

