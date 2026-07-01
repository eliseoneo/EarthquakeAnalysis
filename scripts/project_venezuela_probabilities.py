#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import io
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validation import ROOT, load_yaml
from persistence_store import write_projection_artifacts
from projection_model import (
    MAGNITUDE_MIN_REFERENCE,
    OMORI_C_DAYS,
    calibrate_omori,
    cum_omori,
    observed_horizon_days,
    parse_date,
    probability_m_ge,
    expected_max_magnitude_mw,
)


CASE_2026_PATH = ROOT / "case_library/venezuela_2026/event.yaml"
CASE_1812_PATH = ROOT / "case_library/venezuela_1812/event.yaml"
EVENT_CASE_PATH = ROOT / "event_cases/venezuela_2026_june/event.yaml"

DEFAULT_HORIZONS = (30, 45)
DEFAULT_M_THRESHOLDS = (4.0, 5.0, 6.0)
DEFAULT_USGS_BBOX = {
    "minlatitude": 0.0,
    "maxlatitude": 13.5,
    "minlongitude": -74.5,
    "maxlongitude": -59.5,
}


@dataclass
class ProjectionParams:
    main_date: date
    as_of_date: date
    elapsed_days: int
    omori_p: float
    omori_c_days: float
    omori_K: float
    b_value: float
    magnitude_min_reference: float
    analog_prior_strong_aftershock: float


def _read_yaml(path: Path) -> dict[str, Any]:
    doc = load_yaml(path)
    if not isinstance(doc, dict):
        raise RuntimeError(f"Invalid YAML mapping in {path}")
    return doc


def _build_projection_rows(
    params: ProjectionParams,
    horizons: tuple[int, ...],
    magnitude_thresholds: tuple[float, ...],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon in horizons:
        n_additional = max(
            0.0,
            cum_omori(float(horizon), params.omori_K, params.omori_p, params.omori_c_days)
            - cum_omori(
                float(params.elapsed_days),
                params.omori_K,
                params.omori_p,
                params.omori_c_days,
            ),
        )
        expected_max_mw = expected_max_magnitude_mw(
            n_additional, params.b_value, params.magnitude_min_reference
        )
        probs: dict[str, float] = {}
        for threshold in magnitude_thresholds:
            probs[f"P_M_ge_{threshold:.1f}"] = round(
                probability_m_ge(
                    n_additional,
                    threshold,
                    params.b_value,
                    params.magnitude_min_reference,
                ),
                4,
            )

        likelihood_m6 = probs.get("P_M_ge_6.0", 0.0)
        blended = 0.6 * likelihood_m6 + 0.4 * params.analog_prior_strong_aftershock
        rows.append(
            {
                "horizon_days_from_main": horizon,
                "date_target": (params.main_date + timedelta(days=horizon)).isoformat(),
                "forward_days_from_as_of": max(0, horizon - params.elapsed_days),
                "additional_expected_aftershocks": round(n_additional, 2),
                "expected_max_magnitude_mw": round(expected_max_mw, 2),
                "probabilities": probs,
                "bayesian_blend_strong_aftershock_ge_6_0": round(blended, 4),
            }
        )
    return rows


def _seed_events(
    case_2026: dict[str, Any],
    case_1812: dict[str, Any],
    event_case: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ev in event_case.get("aftershocks", []):
        if not isinstance(ev, dict):
            continue
        rows.append(
            {
                "source": "event_cases/venezuela_2026_june.aftershocks",
                "event_date": ev.get("date", ""),
                "event_time_utc": "",
                "magnitude_mw": ev.get("magnitude_mw", ""),
                "location": ev.get("location", ""),
                "latitude": "",
                "longitude": "",
                "depth_km": ev.get("depth_km", ""),
            }
        )
    for ev in case_2026.get("similar_magnitude_probability_dates", {}).get(
        "highest_magnitude_events", []
    ):
        if not isinstance(ev, dict):
            continue
        rows.append(
            {
                "source": "case_library/venezuela_2026.highest_magnitude_events",
                "event_date": ev.get("event_date", ""),
                "event_time_utc": "",
                "magnitude_mw": ev.get("magnitude_mw", ""),
                "location": "N/A",
                "latitude": "",
                "longitude": "",
                "depth_km": "",
            }
        )
    for ev in case_1812.get("similar_magnitude_probability_dates", {}).get(
        "highest_magnitude_events", []
    ):
        if not isinstance(ev, dict):
            continue
        rows.append(
            {
                "source": "case_library/venezuela_1812.highest_magnitude_events",
                "event_date": ev.get("event_date", ""),
                "event_time_utc": "",
                "magnitude_mw": ev.get("magnitude_mw", ""),
                "location": "N/A (historico)",
                "latitude": "",
                "longitude": "",
                "depth_km": "",
            }
        )
    return rows


def _download_usgs_events(
    start_date: date,
    end_date: date,
    min_magnitude: float,
) -> tuple[list[dict[str, Any]], str]:
    params = {
        "format": "geojson",
        "starttime": start_date.isoformat(),
        "endtime": end_date.isoformat(),
        "minmagnitude": min_magnitude,
        "orderby": "time-asc",
        "limit": 20000,
        **DEFAULT_USGS_BBOX,
    }
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=25) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    features = payload.get("features", [])
    rows: list[dict[str, Any]] = []
    for feat in features:
        if not isinstance(feat, dict):
            continue
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        if not isinstance(props, dict) or not isinstance(geom, dict):
            continue
        coords = geom.get("coordinates", [None, None, None])
        t_ms = props.get("time")
        dt_iso = ""
        if isinstance(t_ms, (int, float)):
            dt_iso = datetime.utcfromtimestamp(float(t_ms) / 1000.0).isoformat() + "Z"
        rows.append(
            {
                "source": "USGS_FDSN",
                "event_date": dt_iso[:10] if dt_iso else "",
                "event_time_utc": dt_iso,
                "magnitude_mw": props.get("mag", ""),
                "location": props.get("place", ""),
                "latitude": coords[1] if len(coords) > 1 else "",
                "longitude": coords[0] if len(coords) > 0 else "",
                "depth_km": coords[2] if len(coords) > 2 else "",
            }
        )
    return rows, f"ok ({len(rows)} eventos)"


def _events_csv_text(rows: list[dict[str, Any]]) -> str:
    headers = [
        "source",
        "event_date",
        "event_time_utc",
        "magnitude_mw",
        "location",
        "latitude",
        "longitude",
        "depth_km",
    ]
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=headers)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in headers})
    return out.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Proyecta probabilidades de replicas y magnitudes para Venezuela "
            "usando Omori-Utsu + Gutenberg-Richter + prior de analogos."
        )
    )
    parser.add_argument(
        "--as-of-date",
        default=date.today().isoformat(),
        help="Fecha de corte (YYYY-MM-DD). Default: hoy.",
    )
    parser.add_argument(
        "--horizons",
        nargs="+",
        type=int,
        default=list(DEFAULT_HORIZONS),
        help="Horizontes (dias desde evento principal). Default: 30 45.",
    )
    parser.add_argument(
        "--min-usgs-magnitude",
        type=float,
        default=3.0,
        help="Magnitud minima para descarga USGS (si se habilita).",
    )
    parser.add_argument(
        "--skip-usgs-download",
        action="store_true",
        help="No descargar eventos USGS; solo exportar datos del repositorio.",
    )
    args = parser.parse_args()

    as_of_date = parse_date(args.as_of_date)
    horizons = tuple(sorted(set(int(h) for h in args.horizons if int(h) > 0)))
    if not horizons:
        raise SystemExit("No valid horizons provided.")

    case_2026 = _read_yaml(CASE_2026_PATH)
    case_1812 = _read_yaml(CASE_1812_PATH)
    event_case = _read_yaml(EVENT_CASE_PATH)

    similarity = case_2026["similar_magnitude_probability_dates"]
    seismic = case_2026["advanced_features"]["seismic"]
    risk_2026 = case_2026["compound_risk_model"]["derived_outputs"]
    risk_1812 = case_1812["compound_risk_model"]["derived_outputs"]

    main_date = parse_date(similarity["main_event_date"])
    observed_horizon = observed_horizon_days(similarity)
    elapsed_days = max(0, (as_of_date - main_date).days)

    p = float(seismic["omori_decay_p"])
    c_days = OMORI_C_DAYS
    K = calibrate_omori(float(seismic["aftershock_count"]), p, observed_horizon, c_days)
    b = float(seismic["gutenberg_richter_b_value"])
    analog_prior = (
        float(risk_2026["probability_strong_aftershock"])
        + float(risk_1812["probability_strong_aftershock"])
    ) / 2.0

    model_params = ProjectionParams(
        main_date=main_date,
        as_of_date=as_of_date,
        elapsed_days=elapsed_days,
        omori_p=p,
        omori_c_days=c_days,
        omori_K=K,
        b_value=b,
        magnitude_min_reference=MAGNITUDE_MIN_REFERENCE,
        analog_prior_strong_aftershock=analog_prior,
    )
    projections = _build_projection_rows(model_params, horizons, DEFAULT_M_THRESHOLDS)

    event_rows = _seed_events(case_2026, case_1812, event_case)
    usgs_status = "skipped"
    if not args.skip_usgs_download:
        try:
            usgs_rows, usgs_status = _download_usgs_events(
                start_date=main_date,
                end_date=as_of_date,
                min_magnitude=args.min_usgs_magnitude,
            )
            event_rows.extend(usgs_rows)
        except Exception as exc:  # noqa: BLE001
            usgs_status = f"failed ({type(exc).__name__}: {exc})"

    csv_content = _events_csv_text(event_rows)

    report = {
        "as_of_date": as_of_date.isoformat(),
        "country": "Venezuela",
        "data_source": [
            str(CASE_2026_PATH.relative_to(ROOT)),
            str(CASE_1812_PATH.relative_to(ROOT)),
            str(EVENT_CASE_PATH.relative_to(ROOT)),
        ],
        "modeling_notes": {
            "models_used": [
                "Omori-Utsu (conteo temporal de replicas)",
                "Gutenberg-Richter (probabilidad por umbral de magnitud)",
                "Bayesian blend simple con prior de analogos (fase 5)",
            ],
            "parameters": {
                "main_event_date": main_date.isoformat(),
                "elapsed_days_from_main": elapsed_days,
                "omori_p": p,
                "omori_c_days": c_days,
                "omori_K": round(K, 4),
                "b_value": b,
                "magnitude_min_reference": MAGNITUDE_MIN_REFERENCE,
                "analog_prior_strong_aftershock": round(analog_prior, 4),
            },
        },
        "projection": projections,
        "usgs_download_status": usgs_status,
        "events_file": f"docs/venezuela_projection_{as_of_date.isoformat()}_events.csv",
    }

    paths = write_projection_artifacts(as_of_date, report, csv_content)
    report["events_file"] = str(paths.docs_csv.relative_to(ROOT))

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
