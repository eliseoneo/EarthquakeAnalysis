#!/usr/bin/env python3
"""CLI — Pipeline Capa A: Tectónica Principal."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from layer_a.pipeline import run_pipeline
from layer_a.paths import DEFAULT_CONFIG, PROCESSED_DIR


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ejecutar pipeline Capa A — Tectónica Principal (datos aislados en layer_a_tectonic/)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Ruta al YAML de configuración",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROCESSED_DIR,
        help="Directorio de salida (parquet, geojson, json)",
    )
    parser.add_argument(
        "--use-fixtures",
        action="store_true",
        default=True,
        help="Usar fixtures sintéticos de layer_a_tectonic/data/fixtures/synthetic/",
    )
    parser.add_argument(
        "--no-fixtures",
        action="store_true",
        help="Solo cargar desde layer_a_tectonic/data/raw/",
    )
    parser.add_argument(
        "--download-usgs",
        action="store_true",
        help="Descargar catálogo USGS FDSN a layer_a_tectonic/data/raw/ antes del pipeline",
    )
    args = parser.parse_args()

    use_fixtures = not args.no_fixtures
    summary = run_pipeline(
        config_path=args.config,
        output_dir=args.output_dir,
        use_fixtures=use_fixtures,
        download_usgs=args.download_usgs,
    )
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
