#!/usr/bin/env python3
"""CLI — Pipeline Capa B: Geofísica Ambiental."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from layer_b.paths import DEFAULT_CONFIG
from layer_b.pipeline import run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pipeline Capa B — Geofísica Ambiental (datos en layer_b_geophysical/)",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--no-synthetic", action="store_true", help="Solo data/raw/")
    args = parser.parse_args()

    summary = run_pipeline(config_path=args.config, use_synthetic=not args.no_synthetic)
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
