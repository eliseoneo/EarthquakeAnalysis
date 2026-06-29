#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validation import ROOT, discover_files, evaluate_feature_coverage, load_document


DEFAULT_PATTERNS = [
    "tests/fixtures/synthetic/venezuela_2026_june_minimal.json",
    "tests/fixtures/synthetic/comparable_event_minimal.json",
]

FULL_PATTERNS = [
    *DEFAULT_PATTERNS,
    "event_cases/**/event.yaml",
    "case_library/**/event.yaml",
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fase 3: evalua cobertura de feature engineering avanzado."
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Incluye event_cases/ y case_library/ ademas de fixtures sinteticos.",
    )
    parser.add_argument(
        "--patterns",
        nargs="+",
        default=None,
        help="Patrones glob de archivos a evaluar",
    )
    parser.add_argument(
        "--fail-under",
        type=float,
        default=95.0,
        help="Umbral minimo de cobertura por archivo (0-100).",
    )
    args = parser.parse_args()

    patterns = args.patterns or (FULL_PATTERNS if args.full else DEFAULT_PATTERNS)
    files = discover_files(patterns)
    if not files:
        print("No files found for Phase 3 evaluation.")
        return 1

    failed = False
    print("Phase 3 evaluation (advanced_features coverage)")
    for file_path in files:
        data = load_document(file_path)
        present, total, missing = evaluate_feature_coverage(data)
        coverage = (present / total) * 100.0
        status = "PASS" if coverage >= args.fail_under else "FAIL"
        print(f"{status} {file_path}: {coverage:.1f}% ({present}/{total})")
        if missing:
            print("  Missing:")
            for item in missing:
                print(f"  - {item}")
        if coverage < args.fail_under:
            failed = True

    if failed:
        print(
            f"\nPhase 3 evaluation failed (threshold {args.fail_under:.1f}%). "
            "Review missing advanced features."
        )
        return 1

    print("\nPhase 3 evaluation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
