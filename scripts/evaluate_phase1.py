#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validation import ROOT, discover_files, validate_document


DEFAULT_PATTERNS = [
    "tests/fixtures/synthetic/venezuela_2026_june_minimal.json",
]

FULL_PATTERNS = [
    *DEFAULT_PATTERNS,
    "event_cases/**/event.yaml",
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fase 1: valida casos post-evento en event_cases/ contra event_case.schema.json."
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Incluye event_cases/ ademas del fixture sintetico.",
    )
    parser.add_argument(
        "--patterns",
        nargs="+",
        default=None,
        help="Patrones glob de archivos a evaluar",
    )
    args = parser.parse_args()

    schema_path = ROOT / "schemas" / "event_case.schema.json"
    patterns = args.patterns or (FULL_PATTERNS if args.full else DEFAULT_PATTERNS)
    files = discover_files(patterns)
    if not files:
        print("No files found for Phase 1 evaluation.")
        return 1

    failed = False
    print("Phase 1 evaluation (event_cases)")
    for file_path in files:
        errors = validate_document(file_path, schema_path)
        if errors:
            failed = True
            print(f"FAIL {file_path}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"PASS {file_path}")

    if failed:
        print("\nPhase 1 evaluation failed.")
        return 1

    print("\nPhase 1 evaluation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
