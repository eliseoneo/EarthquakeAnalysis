#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from international_calculation_workflow import (
    ALTERNATIVE_THRESHOLD_MAGNITUDE,
    PLATT_CALIBRATION_FRACTION,
    WALK_FORWARD_MIN_TRAIN,
    WALK_FORWARD_STEP,
    WALK_FORWARD_TEST_SIZE,
    run_international_estimation,
)


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ejecuta el modelo internacional (Italia/Colombia/USA) sin UI."
    )
    parser.add_argument(
        "--as-of",
        default=date.today().isoformat(),
        help="Fecha de corte YYYY-MM-DD (default: hoy).",
    )
    parser.add_argument("--lookback-days", type=int, default=900)
    parser.add_argument("--window-days", type=int, default=90)
    parser.add_argument("--stride-days", type=int, default=15)
    parser.add_argument("--horizon-days", type=int, default=30)
    parser.add_argument("--threshold-magnitude", type=float, default=5.0)
    parser.add_argument(
        "--alternative-threshold-magnitude",
        type=float,
        default=ALTERNATIVE_THRESHOLD_MAGNITUDE,
        help="Umbral alternativo para etiqueta secundaria (default: 4.5).",
    )
    parser.add_argument("--min-magnitude", type=float, default=3.0)
    parser.add_argument("--walk-forward-min-train", type=int, default=WALK_FORWARD_MIN_TRAIN)
    parser.add_argument("--walk-forward-test-size", type=int, default=WALK_FORWARD_TEST_SIZE)
    parser.add_argument("--walk-forward-step", type=int, default=WALK_FORWARD_STEP)
    parser.add_argument(
        "--no-platt",
        action="store_true",
        help="Desactiva calibracion Platt de probabilidades.",
    )
    parser.add_argument(
        "--platt-calibration-fraction",
        type=float,
        default=PLATT_CALIBRATION_FRACTION,
        help="Fraccion del train reservada para calibracion Platt.",
    )
    parser.add_argument(
        "--no-class-weight",
        action="store_true",
        help="Desactiva balanceo de clases en la logistica.",
    )
    parser.add_argument(
        "--no-live",
        action="store_true",
        help="Desactiva APIs live y usa solo fallback local.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime payload completo en JSON al finalizar.",
    )
    parser.add_argument(
        "--use-live-insar-gnss",
        action="store_true",
        help="Descarga GNSS MIDAS (NGL) y reemplaza filas InSAR proxy.",
    )
    args = parser.parse_args()

    try:
        as_of_date = _parse_date(str(args.as_of).strip())
    except ValueError:
        print("Fecha invalida. Use formato YYYY-MM-DD.")
        return 1

    payload = run_international_estimation(
        as_of_date=as_of_date,
        lookback_days=int(args.lookback_days),
        window_days=int(args.window_days),
        stride_days=int(args.stride_days),
        horizon_days=int(args.horizon_days),
        threshold_magnitude=float(args.threshold_magnitude),
        alternative_threshold_magnitude=float(args.alternative_threshold_magnitude),
        min_magnitude=float(args.min_magnitude),
        use_live_sources=not bool(args.no_live),
        use_live_insar_gnss=bool(args.use_live_insar_gnss),
        walk_forward_min_train=int(args.walk_forward_min_train),
        walk_forward_test_size=int(args.walk_forward_test_size),
        walk_forward_step=int(args.walk_forward_step),
        use_platt_calibration=not bool(args.no_platt),
        platt_calibration_fraction=float(args.platt_calibration_fraction),
        use_class_weight=not bool(args.no_class_weight),
    )

    print(f"status: {payload.get('status', 'unknown')}")
    print(f"message: {payload.get('message', '')}")
    print(f"storage_path: {payload.get('storage_path', '-')}")
    print(f"sources: {len(payload.get('source_table', []))}")
    print(f"metrics: {len(payload.get('metrics_rows', []))}")
    print(f"insar_gnss_rows: {len(payload.get('insar_gnss_rows', []))}")
    bridge = payload.get("geological_insar_bridge", {})
    if bridge:
        print(f"geological_insar_bridge: {bridge.get('status', '-')}")
        print(f"latest_displacement_cm: {bridge.get('latest_displacement_cm', '-')}")
    print(f"anomaly_reference_window: {payload.get('anomaly_reference_window', '-')}")
    print(f"similarity_rows: {len(payload.get('similarity_rows', []))}")
    print(f"walk_forward_folds: {payload.get('walk_forward_folds', 0)}")

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    return 0 if payload.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
