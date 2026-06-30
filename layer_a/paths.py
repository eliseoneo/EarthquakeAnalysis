"""Rutas raíz de Capa A — aisladas de event_cases y case_library."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LAYER_A_ROOT = REPO_ROOT / "layer_a_tectonic"
CONFIG_DIR = LAYER_A_ROOT / "config"
DATA_DIR = LAYER_A_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
FIXTURES_DIR = DATA_DIR / "fixtures" / "synthetic"
REPORTS_DIR = LAYER_A_ROOT / "reports"
SCHEMAS_DIR = LAYER_A_ROOT / "schemas"
DEFAULT_CONFIG = CONFIG_DIR / "default.yaml"
