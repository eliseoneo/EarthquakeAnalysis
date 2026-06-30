"""Carga de catálogos desde fixtures sintéticos o archivos raw."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from layer_a.paths import FIXTURES_DIR, RAW_DIR


def load_json_catalog(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return data.get("events", [])


def load_fixture_catalog(source: str) -> list[dict[str, Any]]:
    path = FIXTURES_DIR / f"catalog_{source}_sample.json"
    if not path.exists():
        return []
    return load_json_catalog(path)


def load_raw_or_fixture(source: str, use_fixtures: bool = True) -> list[dict[str, Any]]:
    raw_path = RAW_DIR / f"catalog_{source}.json"
    if raw_path.exists():
        return load_json_catalog(raw_path)
    if use_fixtures:
        return load_fixture_catalog(source)
    return []
