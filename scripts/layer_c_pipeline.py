#!/usr/bin/env python3
"""CLI — Pipeline Capa C: analisis H04 del evento."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from layer_c.paths import DEFAULT_CONFIG
from layer_c.pipeline import run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pipeline Capa C — Analisis H04 del evento Venezuela 2026",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    summary = run_pipeline(config_path=args.config)
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())