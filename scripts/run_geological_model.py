#!/usr/bin/env python3
"""CLI — Modelo FCN geoespacial geológico (docs/foco-geologico.md)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from geological_model.pipeline import run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ejecuta FCN geoespacial geológico sobre event_cases y case_library.",
    )
    parser.add_argument(
        "--patterns",
        nargs="+",
        default=None,
        help="Patrones glob de casos (default: event_cases, case_library, fixtures).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directorio de salida (default: storage/geological_model/outputs).",
    )
    parser.add_argument(
        "--international-json",
        type=Path,
        default=None,
        help="Payload JSON del workflow internacional con insar_gnss_rows.",
    )
    parser.add_argument(
        "--no-international",
        action="store_true",
        help="No enlazar placeholders InSAR del workflow internacional.",
    )
    args = parser.parse_args()

    summary = run_pipeline(
        patterns=args.patterns,
        output_dir=args.output_dir,
        international_json=args.international_json,
        use_latest_international=not args.no_international,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
