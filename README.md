# EarthquakeAnalysis

Proyecto inicial para analisis sismico con cinco fases activas:

1. Modulo post-evento `event_cases/venezuela_2026_june`.
2. Libreria comparativa global en `case_library`.
3. Feature engineering avanzado:
   - Features sismicas:
     - magnitud
     - profundidad
     - mecanismo focal
     - distancia a falla
     - slip rate estimado
     - PGA / PGV si disponible
     - intensidad MMI
     - numero de replicas
     - decaimiento Omori
     - b-value Gutenberg-Richter
     - densidad sismica local
   - Features geologicas/geotecnicas:
     - tipo de suelo
     - litologia
     - Vs30
     - pendiente
     - cuenca sedimentaria
     - contexto geologico de localizacion
     - fallas geologicas proximas
     - placas tectonicas proximas
     - actividad sismica promedio en fallas proximas
     - eventos relevantes vinculados a fallas proximas
     - licuefaccion probable
     - susceptibilidad a deslizamientos
     - distancia a costa/rios
   - Features climaticas:
     - lluvia acumulada 7/15/30 dias
     - humedad de suelo
     - eventos extremos
     - saturacion del terreno
     - riesgo de remocion en masa
   - Features humanas/urbanas:
     - poblacion expuesta
     - densidad urbana
     - tipo de edificacion
     - altura promedio
     - antiguedad constructiva
     - hospitales
     - vias principales
     - puertos/aeropuertos
     - escuelas
     - infraestructura critica
4. Modelo de riesgo compuesto:
   - Ensemble jerarquico por componentes:
     - amenaza sismica
     - exposicion humana
     - vulnerabilidad estructural
     - vulnerabilidad geotecnica
     - condiciones climaticas
     - criticidad de infraestructura
   - Salida por categoria:
     - riesgo_bajo
     - riesgo_medio
     - riesgo_alto
     - riesgo_critico
   - Salida probabilistica e indices:
     - probabilidad de replica fuerte
     - probabilidad de dano estructural
     - probabilidad de deslizamiento
     - indice de exposicion poblacional
     - indice de colapso urbano relativo
5. Modelos recomendados:
   - Para sismicidad:
     - ETAS
     - Omori-Utsu
     - Gutenberg-Richter
     - Bayesian hierarchical models
     - Hawkes processes
     - Spatio-temporal clustering
   - Para riesgo territorial:
     - XGBoost / LightGBM
     - Random Forest
     - Bayesian networks
     - Graph Neural Networks (si se modelan fallas, ciudades e infraestructura como grafo)
     - Gaussian Processes espaciales
     - Modelos geoespaciales con PySAL
     - FCN geoespacial geologico
     - ConvLSTM InSAR-temporal
     - CNN geoespacial multicapa
   - Para incertidumbre:
     - Monte Carlo
     - Bayesian inference
     - Quantile regression
     - Conformal prediction
     - Sensitivity analysis

Tambien incluye harness minimo para agentes en paralelo (rules + skills) y un area de pruebas con valores sinteticos.

## Capa A — Tectónica Principal (sección aislada)

Pipeline modular para catálogos sísmicos, deduplicación, asociación con fallas/placas, réplicas, dobletes e índices tectónicos. Datos **exclusivos** en `layer_a_tectonic/` — no se mezclan con `event_cases/` ni `case_library/`.

```bash
python3 -m pip install -e ".[dev,layer_a]"
make layer-a-run                              # pipeline con fixtures
make layer-a-run-usgs                        # descarga USGS + pipeline
make layer-a-run-all                         # USGS + INGV + SGC (recomendado)
python3 scripts/layer_a_pipeline.py --download-usgs --download-ingv --download-sgc --no-fixtures
make layer-a-ui                               # UI standalone en :7861
make ui                                       # dashboard unificado en :7860 (incluye pestaña Capa A)
```

Estructura:

- `layer_a/`: paquete Python (normalización, deduplicación, análisis tectónico, salidas).
- `layer_a_tectonic/config/`: configuración YAML.
- `layer_a_tectonic/data/raw/`: catálogos descargados (USGS, FUNVISIS, etc.).
- `layer_a_tectonic/data/fixtures/synthetic/`: datos sintéticos de prueba.
- `layer_a_tectonic/data/processed/`: Parquet, GeoJSON, JSON de salida.
- `layer_a_tectonic/reports/`: reportes Markdown por mainshock.

Salidas esperadas tras `make layer-a-run`:

- `catalog_deduplicated.parquet`
- `catalog_with_faults.parquet`
- `aftershock_sequences.parquet`
- `doublet_candidates.parquet`
- `tectonic_indexes.parquet`
- `reporte_evento_venezuela_2026_06_24.md`

## Capa B — Geofísica Ambiental (sección aislada)

Análisis correlacional y exploratorio de variables astronómicas, atmosféricas, oceánicas, hidrológicas y climáticas. Datos **exclusivos** en `layer_b_geophysical/` — no se mezclan con fases 1-5 ni Capa A.

```bash
python3 -m pip install -e ".[dev,layer_b]"
make layer-b-run                    # pipeline con series sintéticas
make layer-b-ui                     # UI standalone en :7862
make ui                             # dashboard :7860 (pestaña Capa B)
```

Estructura data lake:

- `layer_b_geophysical/data/raw/` — ingesta por conector
- `layer_b_geophysical/data/normalized/` — series normalizadas
- `layer_b_geophysical/data/features/` — feature store
- `layer_b_geophysical/data/analytics/` — correlaciones, clustering, índices
- `layer_b_geophysical/reports/` — reportes Markdown

Conectores: `sst`, `pressure`, `rainfall`, `soil_moisture`, `earth_tides`, `climate_indices`.

Salidas tras `make layer-b-run`:

- `environmental_normalized.parquet`
- `environmental_features.parquet`
- `environmental_indexes.parquet`
- `international_comparison.parquet`
- `correlations.parquet`, `clustering.parquet`
- `reporte_ambiental_venezuela.md`

## Estructura principal

- `AGENTS.md`: lineamientos operativos para agentes.
- `.cursor/rules/`: reglas persistentes del proyecto.
- `.cursor/skills/`: skills del proyecto para ciclo de trabajo.
- `event_cases/`: casos post-evento.
- `case_library/`: eventos analogos historicos/globales.
- `layer_a_tectonic/`: datos y salidas de Capa A (aislados).
- `layer_a/`: código del pipeline tectónico.
- `layer_b_geophysical/`: datos y salidas de Capa B (aislados).
- `layer_b/`: código del pipeline geofísico-ambiental.
- `geological_model/`: paquete FCN geoespacial geológico e integración InSAR/GNSS.
- `models/`: catálogos YAML (Fase 5, FCN, proveedores InSAR/GNSS).
- `storage/`: artefactos operativos (internacional, proyecciones, verificaciones, FCN).
- `schemas/`: contratos JSON Schema.
- `tests/fixtures/synthetic/`: datos sinteticos de prueba.
- `tests/unit/`: validaciones de esquema y consistencia.
- `scripts/`: evaluaciones por fase, pipelines, UI y modelos especializados.

## Uso rapido

```bash
python3 -m pip install -e ".[dev]"
make test
```

## Evaluaciones

```bash
# Validar esquemas y fixtures sinteticos (pytest)
make test

# Fase 1: casos post-evento (event_cases/)
make eval-phase1

# Fase 2: libreria comparativa (case_library/)
make eval-phase2

# Fase 3: cobertura de feature engineering avanzado
make eval-phase3

# Fase 4: cobertura del modelo de riesgo compuesto
make eval-phase4

# Fase 5: catalogo de modelos recomendados
make eval-phase5

# Las 5 fases en secuencia (fixtures sinteticos + catalogo fase 5)
make eval-all

# Auditoria completa con datos reales (event_cases + case_library)
make eval-full

# Evaluacion completa (pytest + fases 1, 2, 3, 4 y 5)
make evaluate
```

Scripts directos:

```bash
python3 scripts/evaluate_phase1.py
python3 scripts/evaluate_phase2.py
python3 scripts/evaluate_phase3.py
python3 scripts/evaluate_phase4.py
python3 scripts/evaluate_phase5.py
python3 scripts/evaluate_all.py
```

## Proyeccion Venezuela diaria

Generar proyeccion de replicas/magnitudes para Venezuela (fecha actual, +30 y +45 dias):

```bash
make project-venezuela
# o
python3 scripts/project_venezuela_probabilities.py
```

Opciones:

```bash
# Fecha de corte manual
python3 scripts/project_venezuela_probabilities.py --as-of-date 2026-06-29

# Horizontes personalizados
python3 scripts/project_venezuela_probabilities.py --horizons 30 45 60

# Solo datos del repositorio (sin descarga USGS)
python3 scripts/project_venezuela_probabilities.py --skip-usgs-download
```

Salidas:

- `docs/venezuela_projection_<YYYY-MM-DD>.json`
- `docs/venezuela_projection_<YYYY-MM-DD>_events.csv`

Persistencia estructurada (nuevo):

- `storage/venezuela/projections/YYYY/MM/DD/projection.json`
- `storage/venezuela/projections/YYYY/MM/DD/events.csv`
- `storage/venezuela/projections/latest/*`
- `storage/venezuela/indices/projections.jsonl`

Verificacion diaria (estimacion de ayer vs valor real de hoy):

```bash
make verify-venezuela-daily
# o
python3 scripts/verify_venezuela_daily_effectiveness.py \
  --estimate-source-date 2026-06-29 \
  --real-values-date 2026-06-30
```

Salidas de verificacion:

- `docs/venezuela_daily_effectiveness_<YYYY-MM-DD>.json`
- `storage/venezuela/verifications/YYYY/MM/DD/verification.json`
- `storage/venezuela/verifications/latest/verification.json`
- `storage/venezuela/indices/verifications.jsonl`

Opciones utiles:

```bash
# Incluir datos reales en cada fase
python3 scripts/evaluate_phase1.py --full
python3 scripts/evaluate_phase2.py --full
python3 scripts/evaluate_phase3.py --full
python3 scripts/evaluate_phase4.py --full

# Ejecutar las 3 fases con datos reales
python3 scripts/evaluate_all.py --full

# Umbral minimo de cobertura Fase 3
python3 scripts/evaluate_phase3.py --fail-under 100

# Patrones personalizados
python3 scripts/evaluate_phase2.py --patterns case_library/chile_2010/event.yaml
```

## Graficas comparativas

Instalar dependencias de interfaz:

```bash
python3 -m pip install -e ".[ui]"
```

Lanzar dashboard Gradio:

```bash
make ui
# o
python3 scripts/comparative_charts.py --host 127.0.0.1 --port 7860
```

La interfaz principal (`make ui`, puerto 7860) organiza pestañas:

1. **Proyección Venezuela 2026** (pestaña inicial):
   - Proyección inicial (`venezuela_2026`, escenario base)
   - Similitudes con otros eventos históricos
   - Efectividad del modelo (hindcast en eventos anteriores, días subsiguientes observados)
   - Calibración automática (K, b) + proyección ajustada para `venezuela_2026`
2. **Análisis comparativo (Fases 1-5)**: barras, dispersión, riesgo, geología, PGA
3. **Calculo y Estimacion Internacional** (layout Fases 1-8):
   - Fuentes internacionales: USGS, INGV, SGC
   - Foco geografico: Venezuela (filtro geoespacial)
   - Evento anomalo de referencia: 2026-06-26
   - Controles de ventana, umbral M≥, umbral alternativo M≥4.5
   - Walk-forward, calibracion Platt, class weight e InSAR MIDAS (NGL)
   - Predicciones M≥5, M≥4.5, excedencia GR y Mmax por cola Gutenberg-Richter
4. **Capa A — Tectónica** y **Capa B — Geofísica Ambiental**

Documentacion detallada de controles UI y marco teorico: `docs/ui_features_and_theory.md`.

## Layout Internacional (Venezuela)

El layout **Calculo y Estimacion Internacional** implementa un flujo metodologico en 8 fases para estimacion dual:

- Clasificacion binaria: probabilidad de ocurrencia de evento con magnitud por encima del umbral (M≥5 y etiqueta alternativa M≥4.5).
- Regresion de cola: magnitud maxima esperada y probabilidad de excedencia via Gutenberg-Richter (no lineal).

### Modelo (ultima version)

- **Features nuevas por ventana:** `max_magnitude_in_window`, `benioff_accel`, `gr_b_delta`, `event_rate_trend`.
- **Clasificacion:** regresion logistica con `class_weight` y calibracion Platt (opcional).
- **Validacion:** walk-forward temporal con umbral operativo calibrado.
- **Mmax:** cola Gutenberg-Richter (`gutenberg_richter_tail`).
- **InSAR/GNSS:** proxy sismico por defecto; MIDAS medido (NGL) con checkbox UI o `--use-live-insar-gnss`.

### Controles UI (pestaña internacional)

| Control | Default | Rol |
|---|---|---|
| Lookback / ventana / stride / horizonte | 900 / 90 / 15 / 30 | Ventanas espacio-temporales |
| Umbral M≥ | 5.0 | Etiqueta principal |
| Umbral alternativo M≥ | 4.5 | Etiqueta secundaria |
| Walk-forward min train / test / step | 8 / 3 / 3 | Validacion cruzada temporal |
| Calibracion Platt | activa | Calibracion de probabilidades |
| Fraccion Platt | 0.2 | Hold-out interno para Platt |
| Class weight | activo | Balanceo de clases |
| InSAR MIDAS (NGL) | inactivo | Sustituye proxy por datos medidos |

### Ejecucion

Por UI:

```bash
make ui
# pestaña "Calculo y Estimacion Internacional" → configurar y ejecutar
```

Por CLI:

```bash
# Basico
make international-estimation

# Con opciones avanzadas
python3 scripts/run_international_estimation.py \
  --as-of 2026-07-01 \
  --alternative-threshold-magnitude 4.5 \
  --walk-forward-min-train 8 \
  --walk-forward-test-size 3 \
  --walk-forward-step 3 \
  --platt-calibration-fraction 0.2 \
  --use-live-insar-gnss

# Desactivar calibracion o class weight
python3 scripts/run_international_estimation.py --no-platt --no-class-weight
```

Integrar InSAR MIDAS al JSON internacional existente:

```bash
make fetch-insar-gnss
# o
python3 scripts/fetch_insar_gnss.py --as-of 2026-07-01
python3 scripts/fetch_insar_gnss.py --international-json storage/venezuela/international/.../international_estimation_*.json
```

Salidas del flujo internacional:

- `storage/venezuela/international/YYYY/MM/DD/international_estimation_<timestamp>.json`
  - `metrics_rows`, `walk_forward_metrics`, `insar_gnss_rows`, `geological_insar_bridge`

## Modelo geologico FCN

Red convolucional geoespacial para riesgo geotecnico, licuacion y acoplamiento con fallas. Conectado al workflow internacional via puente InSAR (`geological_model/insar_bridge.py`).

```bash
make geological-model-run
# o
python3 scripts/run_geological_model.py
python3 scripts/run_geological_model.py \
  --international-json storage/venezuela/international/.../international_estimation_*.json
```

Referencias:

- Configuracion: `models/geological_geospatial_fcn.yaml`
- Marco teorico: `docs/foco-geologico.md`
- Salidas: `storage/geological_model/outputs/latest.json`
- Ventanas MIDAS: `storage/geological_model/raw/insar_gnss_measured_windows.json`

Flujo recomendado (datos instrumentados):

```bash
make international-estimation   # o CLI con --use-live-insar-gnss
make fetch-insar-gnss             # integra MIDAS al JSON internacional
make geological-model-run         # regenera predicciones FCN
```

Caso post-evento `event_cases/venezuela_2026_june/event.yaml` incluye PGA/PGV desde USGS ShakeMap (`us6000t7zp`) para cobertura Fase 3 al 100%.

Persistencia Capa A/B (nuevo, mismo patrón de índices + latest):

- `layer_a_tectonic/persistence/runs/<RUN_ID>/...`
- `layer_a_tectonic/persistence/latest/...`
- `layer_a_tectonic/persistence/index.jsonl`
- `layer_b_geophysical/persistence/runs/<RUN_ID>/...`
- `layer_b_geophysical/persistence/latest/...`
- `layer_b_geophysical/persistence/index.jsonl`

Se genera automáticamente al ejecutar:

- `make layer-a-run`
- `make layer-b-run`
- `make international-estimation`
- `make fetch-insar-gnss`
- `make geological-model-run`

## Referencia rapida de comandos

| Comando | Descripcion |
|---|---|
| `make test` | pytest completo |
| `make evaluate` | pytest + eval fases 1-5 |
| `make eval-full` | auditoria con datos reales |
| `make ui` | dashboard Gradio (:7860) |
| `make international-estimation` | modelo internacional USGS/INGV/SGC |
| `make fetch-insar-gnss` | InSAR/GNSS MIDAS → JSON internacional |
| `make geological-model-run` | FCN geoespacial geologico |
| `make layer-a-run-all` | Capa A con USGS + INGV + SGC |
| `make layer-b-run` | Capa B geofisica ambiental |
| `make project-venezuela` | proyeccion diaria Venezuela |
| `make verify-venezuela-daily` | verificacion estimacion vs observado |

### Detalle pestaña comparativa

- barras comparativas por metrica
- probabilidad de magnitud similar en dias posteriores, usando `similar_magnitude_probability_dates.highest_magnitude_events`
- tabla-resumen con `case_id`, `n_eventos_horizonte`, `n_similares` y `%`
- comparativa de `risk_score_total` y distribucion por `risk_category`
- tabla de riesgo compuesto con `case_id`, `risk_score_total` y `risk_category`
- filtro y tabla tematica por `location_geology_context` (tipo de contexto geologico, litologia, Vs30)
- filtro por placa tectonica y tabla tematica de fallas proximas, actividad promedio y eventos vinculados
- seccion Fase 5 con filtro por dominio (`sismicidad`, `riesgo_territorial`, `incertidumbre`) y tabla de modelos recomendados
- grafica de barras Fase 5 con conteo de modelos recomendados por dominio
- seccion de proyeccion con dias + magnitud objetivo (Mw), probabilidades por caso y tabla con regresion lineal (pendiente y R²)
- pestaña **Capa A — Tectónica** (`layer_a_tectonic/`, pipeline aislado con opción de descarga USGS)
- pestaña **Capa B — Geofísica Ambiental** (`layer_b_geophysical/`, features, índices 0-100 y comparación internacional)

Lanzar con Uvicorn (FastAPI + Gradio montado):

```bash
make ui-uvicorn
# o
python3 scripts/comparative_charts.py --use-uvicorn --host 0.0.0.0 --port 7860
```
