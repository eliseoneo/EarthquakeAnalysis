"""Pipeline del modelo geoespacial geológico."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from geological_model.extractors import discover_event_documents, extract_from_event_document
from geological_model.fcn_model import GeologicalFCNModel
from geological_model.insar_bridge import (
    find_latest_international_payload,
    load_international_payload,
    resolve_insar_from_event_document,
)
from geological_model.paths import OUTPUTS_DIR, REPO_ROOT


def _load_document(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix == ".json":
        return json.loads(text)
    if suffix in {".yaml", ".yml"}:
        import yaml

        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError(f"Expected mapping at root of {path}")
        return data
    raise ValueError(f"Unsupported document format: {path}")


def run_pipeline(
    patterns: list[str] | None = None,
    output_dir: Path | None = None,
    international_json: Path | None = None,
    use_latest_international: bool = True,
) -> dict[str, Any]:
    model = GeologicalFCNModel()
    files = discover_event_documents(REPO_ROOT, patterns)
    out_dir = output_dir or OUTPUTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    international_payload: dict[str, Any] | None = None
    international_source: str | None = None
    if international_json is not None:
        international_payload = load_international_payload(international_json)
        international_source = str(international_json)
    elif use_latest_international:
        latest_path = find_latest_international_payload(REPO_ROOT)
        if latest_path is not None:
            international_payload = load_international_payload(latest_path)
            international_source = str(latest_path)

    predictions: list[dict[str, Any]] = []
    for file_path in files:
        data = _load_document(file_path)
        displacement, quality, bridge_meta = resolve_insar_from_event_document(
            data,
            international_payload,
        )
        features = extract_from_event_document(
            data,
            source_document=str(file_path),
            insar_displacement_cm=displacement,
            insar_quality=quality,
        )
        result = model.predict(features)
        prediction = result.to_flat_dict()
        prediction["insar_bridge"] = {
            **bridge_meta,
            "international_source": international_source,
        }
        predictions.append(prediction)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = out_dir / f"geological_fcn_predictions_{timestamp}.json"
    payload = {
        "model_type": "fcn_geoespacial_geologico",
        "reference_doc": "docs/foco-geologico.md",
        "generated_at_utc": timestamp,
        "cases_evaluated": len(predictions),
        "international_insar_source": international_source,
        "predictions": predictions,
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    latest_path = out_dir / "latest.json"
    latest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "model": "fcn_geoespacial_geologico",
        "cases_evaluated": len(predictions),
        "international_insar_source": international_source,
        "output": str(output_path),
        "latest": str(latest_path),
    }
