#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validation import ROOT, load_yaml

DEFAULT_CONFIG = "models/recommended_models_phase5.yaml"

REQUIRED_MODELS: dict[str, set[str]] = {
    "sismicidad": {
        "ETAS",
        "Omori-Utsu",
        "Gutenberg-Richter",
        "Bayesian hierarchical models",
        "Hawkes processes",
        "Spatio-temporal clustering",
    },
    "riesgo_territorial": {
        "XGBoost",
        "LightGBM",
        "Random Forest",
        "Bayesian networks",
        "Graph Neural Networks",
        "Gaussian Processes espaciales",
        "Modelos geoespaciales con PySAL",
    },
    "incertidumbre": {
        "Monte Carlo",
        "Bayesian inference",
        "Quantile regression",
        "Conformal prediction",
        "Sensitivity analysis",
    },
}


def _normalize_entries(values: object) -> set[str]:
    if not isinstance(values, list):
        return set()
    normalized: set[str] = set()
    for value in values:
        if isinstance(value, str) and value.strip():
            normalized.add(value.strip())
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fase 5: valida catalogo de modelos recomendados por dominio."
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help="Ruta del YAML con recomendaciones de modelos para Fase 5.",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT / config_path

    if not config_path.exists():
        print(f"FAIL {config_path}: configuration file not found")
        return 1

    data = load_yaml(config_path)
    failed = False

    print("Phase 5 evaluation (recommended_models catalog)")
    for category, required in REQUIRED_MODELS.items():
        current = _normalize_entries(data.get(category))
        missing = sorted(required - current)
        status = "PASS" if not missing else "FAIL"
        print(f"{status} {category}: {len(current)}/{len(required)} required models present")
        if missing:
            failed = True
            print("  Missing:")
            for model in missing:
                print(f"  - {model}")

    if failed:
        print(
            "\nPhase 5 evaluation failed. "
            "Review recommended models in models/recommended_models_phase5.yaml."
        )
        return 1

    print("\nPhase 5 evaluation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
