# EarthquakeAnalysis

Initial seismic-analysis project with five active phases plus three isolated analytical layers.

## Active Scope

1. Post-event module in `event_cases/venezuela_2026_june`.
2. Global comparative library in `case_library`.
3. Advanced feature engineering.
4. Compound territorial risk model.
5. Recommended model catalog.
6. Layer A: primary tectonics.
7. Layer B: environmental geophysics.
8. Layer C: H04 event analysis for the Venezuela 24-Jun-2026 earthquake.

## Layer A — Primary Tectonics

Isolated pipeline for seismic catalogs, deduplication, fault/plate association, aftershocks, doublets, and tectonic indexes.

```bash
python3 -m pip install -e ".[dev,layer_a]"
make layer-a-run
make layer-a-run-usgs
make layer-a-run-all
make layer-a-ui
```

Main outputs:

- `catalog_deduplicated.parquet`
- `catalog_with_faults.parquet`
- `aftershock_sequences.parquet`
- `doublet_candidates.parquet`
- `tectonic_indexes.parquet`
- `reporte_evento_venezuela_2026_06_24.md`

## Layer B — Environmental Geophysics

Isolated exploratory and correlation pipeline for oceanic, atmospheric, hydrological, and climate variables.

```bash
python3 -m pip install -e ".[dev,layer_b]"
make layer-b-run
make layer-b-ui
```

Main outputs:

- `environmental_normalized.parquet`
- `environmental_features.parquet`
- `environmental_indexes.parquet`
- `international_comparison.parquet`
- `correlations.parquet`
- `clustering.parquet`
- `reporte_ambiental_venezuela.md`

## Layer C — H04 Event Analysis

Scientific event-analysis layer focused on the 24-Jun-2026 Venezuela earthquake, explicitly separated from any forward projection workflow.

```bash
python3 -m pip install -e ".[dev,ui]"
make layer-c-run
make layer-c-ui
```

Data layout:

- `layer_c_event_analysis/data/raw/accelerography/`: real station-by-station accelerography files when available.
- `layer_c_event_analysis/data/raw/funvisis/`: official FUNVISIS dump when a stable format exists.
- `layer_c_event_analysis/data/normalized/`: normalized accelerography and geotechnical records.
- `layer_c_event_analysis/data/processed/`: linked catalogs, H04 coverage matrix, and derived artifacts.
- `layer_c_event_analysis/schemas/`: JSON Schemas for accelerography and geotechnical records.
- `layer_c_event_analysis/reports/`: H04 report, evidence provenance, and schema reference.

Current ingestion behavior:

- If `layer_c_event_analysis/data/raw/accelerography/accelerography_station_records.json` or `.csv` exists, Layer C uses real station-level accelerography.
- If no real raw accelerography file exists, Layer C bootstraps the dataset from `event_cases/venezuela_2026_june/event.yaml` using `pga_station_estimates`, `pga_g`, and `pgv_cm_per_s`.
- If an official FUNVISIS endpoint or dump is configured in `layer_c_event_analysis/config/default.yaml`, Layer C uses that official source.
- If no official FUNVISIS source is available, Layer C generates a traceable USGS-based fallback proxy marked as `fallback_proxy`.

Validation:

- `tests/test_layer_c.py` validates H04 artifacts.
- The same test validates accelerography and geotechnical JSON records against their JSON Schemas.
- An optional live integration check for external sources is available through `EARTHQUAKEANALYSIS_LIVE_EXTERNAL=1`.
- For live FUNVISIS checks, also configure `EARTHQUAKEANALYSIS_FUNVISIS_ENDPOINT=<url>` or set the official source in `layer_c_event_analysis/config/default.yaml`.

Live test commands:

```bash
# USGS live
cd /Users/eliseogelvis/Projects/EarthquakeAnalysis
EARTHQUAKEANALYSIS_LIVE_EXTERNAL=1 .venv/bin/python -m pytest tests/test_layer_c.py -k usgs_live

# FUNVISIS live (when an official endpoint is available)
cd /Users/eliseogelvis/Projects/EarthquakeAnalysis
EARTHQUAKEANALYSIS_LIVE_EXTERNAL=1 \
EARTHQUAKEANALYSIS_FUNVISIS_ENDPOINT="https://your-funvisis-endpoint" \
.venv/bin/python -m pytest tests/test_layer_c.py -k funvisis_live

# Full live external-source suite
cd /Users/eliseogelvis/Projects/EarthquakeAnalysis
EARTHQUAKEANALYSIS_LIVE_EXTERNAL=1 .venv/bin/python -m pytest tests/test_layer_c.py
```

## Unified UI

Install UI dependencies:

```bash
python3 -m pip install -e ".[ui]"
```

Run the unified Gradio dashboard:

```bash
make ui
```

Main tabs include:

1. Venezuela 2026 projection.
2. Comparative analysis for phases 1-5.
3. International calculation and estimation workflow.
4. Layer C H04 event analysis.
5. Layer A tectonics and Layer B environmental geophysics.

## Quick Start

```bash
python3 -m pip install -e ".[dev]"
make test
```

## Testing

```bash
make test
make eval-phase1
make eval-phase2
make eval-phase3
make eval-phase4
make eval-phase5
make eval-all
make eval-full
make evaluate
```

## Notes

- Spanish operational documentation remains in `README.md`.
- This English file is a maintained companion copy for international collaborators.
