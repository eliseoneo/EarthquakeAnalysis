# Arquitectura Data Lake - EarthquakeAnalysis

## Objetivo

Unificar datos sísmicos, acelerográficos, geodésicos, oceánicos, meteorológicos y satelitales.

## Estructura recomendada

```text
data/
  raw/
    source=USGS/year=2026/month=06/day=24/
    source=FUNVISIS/year=2026/month=06/day=24/
  normalized/
    earthquake_events/
    stations/
    waveforms/
    accelerograms/
    weather/
    satellite/
  curated/
    event_sequences/
    aftershock_windows/
    risk_features/
```

## Tablas principales

- earthquake_events
- event_sources
- focal_mechanisms
- seismic_stations
- waveforms
- accelerograms
- gnss_timeseries
- ocean_timeseries
- weather_reanalysis
- satellite_granules
- fault_catalog
- population_exposure

## Principios

- No sobreescribir raw.
- Versionar normalizaciones.
- Mantener trazabilidad source/event_id.
- Separar datos observados, inferidos y modelados.
- Registrar incertidumbre.
