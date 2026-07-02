"""Rutas del modelo geoespacial geológico."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = REPO_ROOT / "models"
DEFAULT_CONFIG = CONFIG_DIR / "geological_geospatial_fcn.yaml"
INSAR_GNSS_CONFIG = CONFIG_DIR / "insar_gnss_providers.yaml"
STORAGE_ROOT = REPO_ROOT / "storage" / "geological_model"
RAW_DIR = STORAGE_ROOT / "raw"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "geological"
OUTPUTS_DIR = STORAGE_ROOT / "outputs"
MEASURED_WINDOWS_FILE = RAW_DIR / "insar_gnss_measured_windows.json"
