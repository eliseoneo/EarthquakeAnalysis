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

from international_calculation_workflow import run_international_estimation


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
    parser.add_argument("--min-magnitude", type=float, default=3.0)
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
        min_magnitude=float(args.min_magnitude),
        use_live_sources=not bool(args.no_live),
    )

    print(f"status: {payload.get('status', 'unknown')}")
    print(f"message: {payload.get('message', '')}")
    print(f"storage_path: {payload.get('storage_path', '-')}")
    print(f"sources: {len(payload.get('source_table', []))}")
    print(f"metrics: {len(payload.get('metrics_rows', []))}")
    print(f"insar_gnss_rows: {len(payload.get('insar_gnss_rows', []))}")
    print(f"anomaly_reference_window: {payload.get('anomaly_reference_window', '-')}")
    print(f"similarity_rows: {len(payload.get('similarity_rows', []))}")

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    return 0 if payload.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
