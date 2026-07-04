"""Carga de configuracion YAML — Capa C."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from layer_c.paths import DEFAULT_CONFIG


def load_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or DEFAULT_CONFIG
    with config_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)