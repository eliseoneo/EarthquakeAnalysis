"""Rutas raiz de Capa C — analisis del evento H04 aislado de proyecciones."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LAYER_C_ROOT = REPO_ROOT / "layer_c_event_analysis"
CONFIG_DIR = LAYER_C_ROOT / "config"
DATA_DIR = LAYER_C_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
NORMALIZED_DIR = DATA_DIR / "normalized"
PROCESSED_DIR = DATA_DIR / "processed"
SCHEMAS_DIR = LAYER_C_ROOT / "schemas"
REPORTS_DIR = LAYER_C_ROOT / "reports"
PERSISTENCE_DIR = LAYER_C_ROOT / "persistence"
DEFAULT_CONFIG = CONFIG_DIR / "default.yaml"
REFERENCE_DOC = REPO_ROOT / "docs" / "H04_Hipotesis_Superposicion_Energia_Venezuela_2026.md"