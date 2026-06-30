from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

PHASE3_FEATURE_PATHS: tuple[tuple[str, ...], ...] = (
    ("advanced_features", "seismic", "magnitude_mw"),
    ("advanced_features", "seismic", "depth_km"),
    ("advanced_features", "seismic", "focal_mechanism"),
    ("advanced_features", "seismic", "distance_to_fault_km"),
    ("advanced_features", "seismic", "estimated_slip_rate_mm_per_year"),
    ("advanced_features", "seismic", "pga_g"),
    ("advanced_features", "seismic", "pgv_cm_per_s"),
    ("advanced_features", "seismic", "mmi_intensity"),
    ("advanced_features", "seismic", "aftershock_count"),
    ("advanced_features", "seismic", "omori_decay_p"),
    ("advanced_features", "seismic", "gutenberg_richter_b_value"),
    ("advanced_features", "seismic", "local_seismic_density"),
    ("advanced_features", "geological_geotechnical", "soil_type"),
    ("advanced_features", "geological_geotechnical", "lithology"),
    ("advanced_features", "geological_geotechnical", "vs30_m_per_s"),
    ("advanced_features", "geological_geotechnical", "slope_degrees"),
    ("advanced_features", "geological_geotechnical", "sedimentary_basin"),
    ("advanced_features", "geological_geotechnical", "location_geology_context"),
    ("advanced_features", "geological_geotechnical", "nearby_geological_faults"),
    ("advanced_features", "geological_geotechnical", "nearby_tectonic_plates"),
    (
        "advanced_features",
        "geological_geotechnical",
        "faults_average_seismic_activity_events_per_year",
    ),
    ("advanced_features", "geological_geotechnical", "fault_linked_relevant_events"),
    ("advanced_features", "geological_geotechnical", "liquefaction_likelihood"),
    ("advanced_features", "geological_geotechnical", "landslide_susceptibility"),
    ("advanced_features", "geological_geotechnical", "distance_to_coast_or_rivers_km"),
    ("advanced_features", "climatic", "rainfall_7d_mm"),
    ("advanced_features", "climatic", "rainfall_15d_mm"),
    ("advanced_features", "climatic", "rainfall_30d_mm"),
    ("advanced_features", "climatic", "soil_moisture_index"),
    ("advanced_features", "climatic", "extreme_events"),
    ("advanced_features", "climatic", "terrain_saturation"),
    ("advanced_features", "climatic", "mass_movement_risk"),
    ("advanced_features", "human_urban", "exposed_population"),
    ("advanced_features", "human_urban", "urban_density"),
    ("advanced_features", "human_urban", "building_type"),
    ("advanced_features", "human_urban", "average_building_height_m"),
    ("advanced_features", "human_urban", "construction_age_profile"),
    ("advanced_features", "human_urban", "hospitals_count"),
    ("advanced_features", "human_urban", "primary_roads_density_km_per_km2"),
    ("advanced_features", "human_urban", "ports_airports_access"),
    ("advanced_features", "human_urban", "schools_count"),
    ("advanced_features", "human_urban", "critical_infrastructure"),
)

PHASE4_RISK_PATHS: tuple[tuple[str, ...], ...] = (
    ("compound_risk_model", "model_type"),
    ("compound_risk_model", "component_scores", "seismic_hazard"),
    ("compound_risk_model", "component_scores", "human_exposure"),
    ("compound_risk_model", "component_scores", "structural_vulnerability"),
    ("compound_risk_model", "component_scores", "geotechnical_vulnerability"),
    ("compound_risk_model", "component_scores", "climatic_conditions"),
    ("compound_risk_model", "component_scores", "infrastructure_criticality"),
    ("compound_risk_model", "risk_score_total"),
    ("compound_risk_model", "risk_category"),
    ("compound_risk_model", "derived_outputs", "probability_strong_aftershock"),
    ("compound_risk_model", "derived_outputs", "probability_structural_damage"),
    ("compound_risk_model", "derived_outputs", "probability_landslide"),
    ("compound_risk_model", "derived_outputs", "population_exposure_index"),
    ("compound_risk_model", "derived_outputs", "relative_urban_collapse_index"),
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required for YAML evaluation. Install with: pip install -e '.[dev]'"
        ) from exc

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping at root of {path}")
    return data


def load_document(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return load_json(path)
    if suffix in {".yaml", ".yml"}:
        return load_yaml(path)
    raise ValueError(f"Unsupported document format: {path}")


def _type_matches(value: Any, expected_type: str | list[str]) -> bool:
    if isinstance(expected_type, list):
        return any(_type_matches(value, item) for item in expected_type)

    if expected_type == "null":
        return value is None
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    return True


def _validate_node(
    schema: dict[str, Any],
    data: Any,
    path: str,
    errors: list[str],
) -> None:
    expected_type = schema.get("type")
    if expected_type is not None and not _type_matches(data, expected_type):
        errors.append(f"{path}: expected type {expected_type}, got {type(data).__name__}")
        return

    if not isinstance(data, dict):
        return

    for field in schema.get("required", []):
        if field not in data:
            errors.append(f"{path}.{field}: missing required field")

    properties = schema.get("properties", {})
    for field, definition in properties.items():
        if field not in data:
            continue
        child_path = f"{path}.{field}" if path else field
        child_data = data[field]
        child_type = definition.get("type")

        if child_type is not None and not _type_matches(child_data, child_type):
            errors.append(
                f"{child_path}: expected type {child_type}, got {type(child_data).__name__}"
            )
            continue

        if definition.get("type") == "object" or (
            isinstance(child_type, list) and "object" in child_type
        ):
            if isinstance(child_data, dict):
                _validate_node(definition, child_data, child_path, errors)

        if definition.get("type") == "array" and "items" in definition:
            if not isinstance(child_data, list):
                continue
            item_schema = definition["items"]
            if item_schema.get("type") == "object":
                for index, item in enumerate(child_data):
                    item_path = f"{child_path}[{index}]"
                    if isinstance(item, dict):
                        _validate_node(item_schema, item, item_path, errors)
                    else:
                        errors.append(
                            f"{item_path}: expected object, got {type(item).__name__}"
                        )


def validate_against_schema(data: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _validate_node(schema, data, "", errors)
    return errors


def validate_document(path: Path, schema_path: Path) -> list[str]:
    schema = load_json(schema_path)
    data = load_document(path)
    return validate_against_schema(data, schema)


def read_path(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    cursor: Any = data
    for key in path:
        if not isinstance(cursor, dict) or key not in cursor:
            return None
        cursor = cursor[key]
    return cursor


def is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def path_exists(data: dict[str, Any], path: tuple[str, ...]) -> bool:
    cursor: Any = data
    for key in path:
        if not isinstance(cursor, dict) or key not in cursor:
            return False
        cursor = cursor[key]
    return True


def evaluate_feature_coverage(
    data: dict[str, Any],
    feature_paths: tuple[tuple[str, ...], ...] = PHASE3_FEATURE_PATHS,
) -> tuple[int, int, list[str]]:
    missing: list[str] = []
    for feature_path in feature_paths:
        if not path_exists(data, feature_path):
            missing.append(".".join(feature_path))

    total = len(feature_paths)
    present = total - len(missing)
    return present, total, missing


def evaluate_risk_model_coverage(
    data: dict[str, Any],
    risk_paths: tuple[tuple[str, ...], ...] = PHASE4_RISK_PATHS,
) -> tuple[int, int, list[str]]:
    missing: list[str] = []
    for risk_path in risk_paths:
        if not path_exists(data, risk_path):
            missing.append(".".join(risk_path))

    total = len(risk_paths)
    present = total - len(missing)
    return present, total, missing


def discover_files(patterns: list[str], root: Path = ROOT) -> list[Path]:
    discovered: list[Path] = []
    for pattern in patterns:
        discovered.extend(sorted(root.glob(pattern)))
    return discovered
