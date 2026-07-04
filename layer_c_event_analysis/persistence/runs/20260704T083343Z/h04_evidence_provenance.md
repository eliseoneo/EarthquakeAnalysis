# Procedencia de Evidencia H04

## Catalogo sismico
- USGS: estado=available_raw, modo=layer_a_raw_and_processed, procesados=8001
- FUNVISIS: estado=fixture_only, modo=layer_a_fixture_and_processed, procesados=0

## FUNVISIS
- Estrategia actual: fallback_proxy
- Modo: usgs_proxy_for_funvisis
- Fuente utilizada: USGS proxy for FUNVISIS
- Notas: Fallback temporal mientras no exista conector oficial FUNVISIS.
- Endpoint observado: https://www.funvisis.gob.ve/maravilla.json
- Estructura observada: FeatureCollection tipo GeoJSON con eventos recientes.
- Limitaciones: sin filtros documentados y cobertura historica aparente limitada.

## Acelerografia
- Registros raw: 2
- Archivo raw: /Users/eliseogelvis/Projects/EarthquakeAnalysis/layer_c_event_analysis/data/raw/accelerography/accelerography_station_estimates.json
- Archivo normalizado: /Users/eliseogelvis/Projects/EarthquakeAnalysis/layer_c_event_analysis/data/normalized/accelerography_station_records.json
- Procedencia: archivo raw por estacion si existe; en ausencia de este, bootstrap desde pga_station_estimates y campos PGA/PGV del caso Venezuela 2026.

## Geotecnia
- Registros normalizados: 1
- Archivo normalizado: /Users/eliseogelvis/Projects/EarthquakeAnalysis/layer_c_event_analysis/data/normalized/geotechnical_site_records.json
- Procedencia: advanced_features.geological_geotechnical del caso Venezuela 2026.