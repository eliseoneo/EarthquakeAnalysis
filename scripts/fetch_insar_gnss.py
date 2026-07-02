#!/usr/bin/env python3
"""CLI — Obtener InSAR/GNSS medidos y reemplazar filas proxy."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from geological_model.insar_bridge import (
    STATUS_MEASURED,
    build_insar_gnss_rows,
    load_international_payload,
)
from geological_model.insar_gnss_fetch import (
    apply_insar_replacement_to_payload,
    fetch_and_replace_from_international_payload,
    fetch_and_replace_insar_gnss_rows,
    fetch_and_replace_international_payload_file,
    fetch_measured_insar_gnss_rows,
    find_international_payload_for_date,
    persist_international_payload,
    persist_measured_rows,
    window_stubs_from_rows,
)
from geological_model.paths import MEASURED_WINDOWS_FILE, REPO_ROOT
from international_calculation_workflow import build_window_dataset, load_international_events


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _resolve_international_path(
    explicit_path: Path | None,
    as_of_date: date,
) -> Path | None:
    if explicit_path is not None:
        return explicit_path
    return find_international_payload_for_date(REPO_ROOT, as_of_date)


def _build_samples(as_of_date: date, args: argparse.Namespace):
    events, _ = load_international_events(
        as_of_date=as_of_date,
        lookback_days=args.lookback_days,
        min_magnitude=args.min_magnitude,
        use_live_sources=False,
    )
    return build_window_dataset(
        events,
        as_of_date=as_of_date,
        lookback_days=args.lookback_days,
        window_days=args.window_days,
        stride_days=args.stride_days,
        horizon_days=args.horizon_days,
        threshold_magnitude=args.threshold_magnitude,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Obtiene VSR/SSR/NSR medidos (GNSS MIDAS NGL) y reemplaza filas proxy.",
    )
    parser.add_argument(
        "--international-json",
        type=Path,
        default=None,
        help="Payload internacional existente con insar_gnss_rows proxy.",
    )
    parser.add_argument(
        "--as-of",
        default=date.today().isoformat(),
        help="Fecha de corte para reconstruir ventanas si no hay JSON de entrada.",
    )
    parser.add_argument("--lookback-days", type=int, default=900)
    parser.add_argument("--window-days", type=int, default=90)
    parser.add_argument("--stride-days", type=int, default=15)
    parser.add_argument("--horizon-days", type=int, default=30)
    parser.add_argument("--threshold-magnitude", type=float, default=5.0)
    parser.add_argument("--min-magnitude", type=float, default=3.0)
    parser.add_argument(
        "--local-measured",
        type=Path,
        default=None,
        help="Archivo JSON local con ventanas medidas.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=MEASURED_WINDOWS_FILE,
        help="Ruta de salida para ventanas medidas persistidas.",
    )
    parser.add_argument(
        "--no-live",
        action="store_true",
        help="No descargar NGL; usar solo archivo local si existe.",
    )
    parser.add_argument(
        "--fetch-only",
        action="store_true",
        help="Solo obtener filas medidas, sin reemplazar payload de entrada.",
    )
    parser.add_argument(
        "--no-update-international",
        action="store_true",
        help="No actualizar el JSON internacional guardado.",
    )
    args = parser.parse_args()

    as_of_date = _parse_date(str(args.as_of).strip())
    international_path = _resolve_international_path(args.international_json, as_of_date)
    update_international = not args.no_update_international
    use_live = not args.no_live

    if args.fetch_only:
        if international_path is not None and international_path.exists():
            payload = load_international_payload(international_path)
            stubs = window_stubs_from_rows(payload.get("insar_gnss_rows", []))
        else:
            stubs = _build_samples(as_of_date, args)
        measured_rows, fetch_meta = fetch_measured_insar_gnss_rows(
            stubs,
            use_live=use_live,
            local_measured_path=args.local_measured,
            max_rows=len(stubs),
        )
        out_path = persist_measured_rows(measured_rows, args.output)
        print(
            json.dumps(
                {"fetch": fetch_meta, "output": str(out_path), "measured_rows": len(measured_rows)},
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    international_updated: str | None = None
    replaced_rows: list[list]
    fetch_replace_meta: dict

    if international_path is not None and international_path.exists():
        if update_international:
            saved_path, replaced_rows, fetch_replace_meta = fetch_and_replace_international_payload_file(
                international_path,
                use_live=use_live,
                local_measured_path=args.local_measured,
                update_file=True,
            )
            international_updated = str(saved_path)
        else:
            payload = load_international_payload(international_path)
            replaced_rows, fetch_replace_meta = fetch_and_replace_from_international_payload(
                payload,
                use_live=use_live,
                local_measured_path=args.local_measured,
            )
    else:
        samples = _build_samples(as_of_date, args)
        proxy_rows = build_insar_gnss_rows(samples)
        replaced_rows, fetch_replace_meta = fetch_and_replace_insar_gnss_rows(
            samples,
            proxy_rows=proxy_rows,
            use_live=use_live,
            local_measured_path=args.local_measured,
        )
        if update_international and international_path is not None and international_path.exists():
            payload = load_international_payload(international_path)
            updated = apply_insar_replacement_to_payload(payload, replaced_rows, fetch_replace_meta)
            persist_international_payload(international_path, updated)
            international_updated = str(international_path)

    out_path = persist_measured_rows(
        [row for row in replaced_rows if len(row) > 5 and row[5] == STATUS_MEASURED],
        args.output,
    )
    summary = {
        "rows_total": len(replaced_rows),
        "rows_measured": sum(
            1 for row in replaced_rows if len(row) > 5 and row[5] == STATUS_MEASURED
        ),
        "rows_proxy": sum(
            1 for row in replaced_rows if len(row) <= 5 or row[5] != STATUS_MEASURED
        ),
        "fetch_replace": fetch_replace_meta,
        "measured_output": str(out_path),
        "international_json_updated": international_updated,
        "insar_gnss_rows": replaced_rows,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
