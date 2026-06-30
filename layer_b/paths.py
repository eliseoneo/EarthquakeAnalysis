"""Rutas raíz de Capa B — aisladas de fases 1-5 y Capa A."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LAYER_B_ROOT = REPO_ROOT / "layer_b_geophysical"
CONFIG_DIR = LAYER_B_ROOT / "config"
DATA_DIR = LAYER_B_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
NORMALIZED_DIR = DATA_DIR / "normalized"
FEATURES_DIR = DATA_DIR / "features"
ANALYTICS_DIR = DATA_DIR / "analytics"
FIXTURES_DIR = DATA_DIR / "fixtures" / "synthetic"
REPORTS_DIR = LAYER_B_ROOT / "reports"
DEFAULT_CONFIG = CONFIG_DIR / "default.yaml"
