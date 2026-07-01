#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from persistence_store import ROOT, projection_paths, write_verification_artifact
from projection_model import cum_omori, parse_date, probability_m_ge


def _load_projection_for_date(source_date: date) -> dict[str, Any]:
    paths = projection_paths(source_date)
    candidates = [
        paths.store_json,
        paths.docs_json,
    ]
    for candidate in candidates:
        if candidate.exists():
            data = json.loads(candidate.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    raise FileNotFoundError(
        f"No se encontro proyeccion para {source_date.isoformat()} en storage/docs."
    )


def _fetch_usgs_events(start_date: date, end_date: date) -> list[dict[str, Any]]:
    base = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    query = (
        "format=geojson"
        f"&starttime={start_date.isoformat()}"
        f"&endtime={end_date.isoformat()}"
        "&minlatitude=0.0&maxlatitude=13.5&minlongitude=-74.5&maxlongitude=-59.5"
        "&orderby=time-asc&limit=20000"
    )
    url = f"{base}?{query}"
    raw = subprocess.check_output(["curl", "-s", url], text=True)
    payload = json.loads(raw)
    features = payload.get("features", []) if isinstance(payload, dict) else []
    return [f for f in features if isinstance(f, dict)]


def _extract_magnitudes(features: list[dict[str, Any]]) -> list[float]:
    magnitudes: list[float] = []
    for feature in features:
        props = feature.get("properties", {})
        if not isinstance(props, dict):
            continue
        mag = props.get("mag")
        if isinstance(mag, (int, float)):
            magnitudes.append(float(mag))
    return magnitudes


def _incremental_prediction_1d(projection: dict[str, Any]) -> tuple[float, dict[float, float]]:
    params = projection.get("modeling_notes", {}).get("parameters", {})
    K = float(params["omori_K"])
    omori_p = float(params["omori_p"])
    c_days = float(params["omori_c_days"])
    b_value = float(params["b_value"])
    m_ref = float(params["magnitude_min_reference"])
    elapsed = int(params["elapsed_days_from_main"])

    n_additional = max(
        0.0,
        cum_omori(float(elapsed + 1), K, omori_p, c_days)
        - cum_omori(float(elapsed), K, omori_p, c_days),
    )
    thresholds = (4.0, 5.0, 6.0)
    probs = {
        threshold: float(probability_m_ge(n_additional, threshold, b_value, m_ref))
        for threshold in thresholds
    }
    return n_additional, probs


def build_report(
    estimate_source_date: date,
    real_values_date: date,
) -> dict[str, Any]:
    projection = _load_projection_for_date(estimate_source_date)
    n_additional, probs = _incremental_prediction_1d(projection)

    features = _fetch_usgs_events(real_values_date, real_values_date + timedelta(days=1))
    magnitudes = _extract_magnitudes(features)
    max_mag_today = max(magnitudes) if magnitudes else None

    metrics: list[dict[str, Any]] = []
    for threshold in (4.0, 5.0, 6.0):
        y = 1 if (max_mag_today is not None and max_mag_today >= threshold) else 0
        p = probs[threshold]
        brier = (p - y) ** 2
        pred_label = 1 if p >= 0.5 else 0
        metrics.append(
            {
                "threshold_mw": threshold,
                "predicted_probability": round(p, 6),
                "observed_event_reached": bool(y),
                "observed_binary": y,
                "predicted_binary_at_0_5": pred_label,
                "hit": bool(pred_label == y),
                "brier_score": round(brier, 6),
                "absolute_error": round(abs(p - y), 6),
            }
        )

    mean_brier = sum(item["brier_score"] for item in metrics) / len(metrics)
    mean_abs_error = sum(item["absolute_error"] for item in metrics) / len(metrics)
    accuracy = sum(1 for item in metrics if item["hit"]) / len(metrics)

    query_url = (
        "https://earthquake.usgs.gov/fdsnws/event/1/query"
        f"?format=geojson&starttime={real_values_date.isoformat()}"
        f"&endtime={(real_values_date + timedelta(days=1)).isoformat()}"
        "&minlatitude=0.0&maxlatitude=13.5&minlongitude=-74.5&maxlongitude=-59.5"
        "&orderby=time-asc&limit=20000"
    )

    report = {
        "verification_date": real_values_date.isoformat(),
        "comparison": {
            "estimate_source_date": estimate_source_date.isoformat(),
            "estimate_source_file": f"docs/venezuela_projection_{estimate_source_date.isoformat()}.json",
            "real_values_date": real_values_date.isoformat(),
        },
        "model_incremental_prediction_1d": {
            "from_date": estimate_source_date.isoformat(),
            "to_date": real_values_date.isoformat(),
            "additional_expected_aftershocks": round(n_additional, 6),
            "probabilities_by_threshold": {
                f"M>={threshold:.1f}": round(probabilities, 6)
                for threshold, probabilities in probs.items()
            },
        },
        "observed_real_values_today": {
            "source": "USGS FDSN GeoJSON",
            "query_url": query_url,
            "events_count_all_magnitudes": len(features),
            "max_magnitude_mw": max_mag_today,
            "events_count_m_ge_4_0": sum(1 for x in magnitudes if x >= 4.0),
            "events_count_m_ge_5_0": sum(1 for x in magnitudes if x >= 5.0),
            "events_count_m_ge_6_0": sum(1 for x in magnitudes if x >= 6.0),
        },
        "effectiveness_metrics": {
            "threshold_metrics": metrics,
            "mean_brier_score": round(mean_brier, 6),
            "mean_absolute_error": round(mean_abs_error, 6),
            "binary_accuracy_at_0_5_threshold": round(accuracy, 6),
        },
        "interpretation": {
            "summary": (
                "Verificacion diaria generada con comparacion entre estimacion del dia previo "
                "y observacion real del dia actual en bbox Venezuela."
            ),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verifica efectividad diaria de la proyeccion Venezuela: "
            "estimacion de ayer vs valor real de hoy (USGS)."
        )
    )
    parser.add_argument(
        "--estimate-source-date",
        default=(date.today() - timedelta(days=1)).isoformat(),
        help="Fecha de la proyeccion base (YYYY-MM-DD). Default: ayer.",
    )
    parser.add_argument(
        "--real-values-date",
        default=date.today().isoformat(),
        help="Fecha de observacion real (YYYY-MM-DD). Default: hoy.",
    )
    args = parser.parse_args()

    estimate_source_date = parse_date(args.estimate_source_date)
    real_values_date = parse_date(args.real_values_date)

    report = build_report(estimate_source_date, real_values_date)
    paths = write_verification_artifact(real_values_date, report)

    report["persistence"] = {
        "docs_json": str(paths.docs_json.relative_to(ROOT)),
        "store_json": str(paths.store_json.relative_to(ROOT)),
        "latest_json": str(paths.latest_json.relative_to(ROOT)),
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
