# Diccionario de campos de la UI — EarthquakeAnalysis

Referencia operativa de **cada medición, columna y control** que aparece en el dashboard Gradio (`make ui`, puerto `:7860`).

- **Implementación UI:** `scripts/comparative_charts.py`, `scripts/venezuela_projection_workflow.py`, `scripts/international_calculation_workflow.py`, `layer_a/ui.py`, `layer_b/ui.py`
- **Marco teórico ampliado:** `docs/ui_features_and_theory.md`
- **Contratos de datos:** `schemas/event_case.schema.json`, `schemas/comparable_event.schema.json`
- **Fuente principal de casos comparativos:** `case_library/*/event.yaml`

---

## Índice

1. [Pestaña Proyección Venezuela 2026](#1-pestaña-proyección-venezuela-2026)
2. [Pestaña Cálculo y Estimación Internacional](#2-pestaña-cálculo-y-estimación-internacional)
3. [Pestaña Análisis comparativo (Fases 1–5)](#3-pestaña-análisis-comparativo-fases-15)
4. [Pestaña Capa A — Tectónica Principal](#4-pestaña-capa-a--tectónica-principal)
5. [Pestaña Capa B — Geofísica Ambiental](#5-pestaña-capa-b--geofísica-ambiental)
6. [Valores categóricos y enums](#6-valores-categóricos-y-enums)
7. [Campos fuera de la UI (relacionados)](#7-campos-fuera-de-la-ui-relacionados)

---

## 1. Pestaña Proyección Venezuela 2026

Flujo en cinco pasos: proyección inicial → similitud histórica → efectividad (hindcast) → proyección calibrada → verificación diaria.

### 1.1 Controles

| Control UI | Campo interno | Unidad / rango | Descripción |
|---|---|---|---|
| Fecha de corte (YYYY-MM-DD) | `as_of_date` | fecha ISO | Día desde el cual se proyecta hacia adelante. No es el día del mainshock. |
| Días forward | `forward_days` | 1–120 días | Ventana futura a estimar **desde la fecha de corte**. |
| Días validación hindcast | `validation_days` | 1–120 días | Ventana retrospectiva para medir certeza del modelo contra eventos ya observados. |
| Magnitud objetivo (Mw) | `magnitude_target_mw` | 4.0–9.5 | Umbral M para calcular P(M ≥ umbral). |
| Horizonte similitud (días) | `horizon_days` | 1–365 días | Ventana post-mainshock para comparar magnitudes similares entre casos históricos. |

### 1.2 Tabla de proyección (`PROJECTION_TABLE_HEADERS`)

Usada en **proyección inicial** y **proyección calibrada** para el caso `venezuela_2026`.

| Columna UI | Campo | Unidad | Descripción |
|---|---|---|---|
| `case_id` | `case_id` | — | Identificador del caso (`venezuela_2026` en este flujo). |
| `scenario` | `scenario` | enum | Escenario Omori/G-R: `base`, `conservador`, `optimista` (calibrado solo en paso 4). |
| `as_of_date` | `as_of_date` | fecha | Fecha de corte seleccionada. |
| `elapsed_days` | `elapsed_days_from_main` | días | Días transcurridos entre mainshock y fecha de corte. |
| `forward_days` | `forward_days` | días | Días proyectados hacia adelante desde la fecha de corte. |
| `magnitude_target_mw` | `magnitude_target_mw` | Mw | Magnitud umbral definida por el usuario. |
| `omori_K` | `omori_K` | adimensional | Constante K de la ley Omori-Utsu ajustada al caso y escenario. |
| `b_value` | `b_value` | adimensional | Pendiente b de Gutenberg-Richter en la ventana modelada. |
| `expected_aftershocks` | `additional_expected_aftershocks` | eventos | Número esperado de réplicas en la ventana forward (Omori). |
| `expected_max_mw` | `expected_max_magnitude_mw` | Mw | Magnitud máxima esperada vía relación G-R y conteo acumulado. |
| `probability_m_ge_target` | `probability_m_ge_target` | 0–1 (UI: %) | Probabilidad de al menos un evento M ≥ objetivo en la ventana forward (Poisson + G-R). |
| `observed_max_mw` | `observed_max_magnitude_mw` | Mw | Máxima magnitud observada en catálogo hasta `as_of_date`. |

**Gráficas asociadas:** barras de P(M ≥ objetivo) por escenario o paso del flujo.

### 1.3 Tabla de similitud histórica

| Columna UI | Campo | Unidad | Descripción |
|---|---|---|---|
| `case_id` | `case_id` | — | Caso de `case_library` comparado con `venezuela_2026`. |
| `n_eventos_horizonte` | conteo | eventos | Eventos en `highest_magnitude_events` dentro del horizonte post-mainshock. |
| `n_similares` | conteo | eventos | Eventos con \|M − M_ref\| ≤ ΔM dentro del horizonte. |
| `%` | probabilidad empírica | % | `n_similares / n_eventos_horizonte × 100`. Análisis frecuentista, no bayesiano. |

**Fuente de datos:** `similar_magnitude_probability_dates` en cada `event.yaml`.

### 1.4 Tabla de efectividad (hindcast)

| Columna UI | Campo | Unidad | Descripción |
|---|---|---|---|
| `case_id` | `case_id` | — | Caso histórico evaluado. |
| `model_name` | `model_name` | — | Identificador del modelo de proyección (`omori_gr_forward`). |
| `scenario` | `scenario` | enum | Escenario Omori/G-R usado en la validación. |
| `validation_days` | `validation_days` | días | Ventana retrospectiva de validación. |
| `magnitude_target_mw` | `magnitude_target_mw` | Mw | Umbral M del hindcast. |
| `predicted_probability_m_ge_target` | `predicted_probability` | 0–1 | Probabilidad modelada de M ≥ umbral en la ventana. |
| `observed_event_reached` | binario | 0/1 | 1 si ocurrió al menos un evento M ≥ umbral en la ventana; 0 si no. |
| `observed_max_magnitude_mw` | `observed_max_mw` | Mw | Máxima magnitud observada en la ventana de validación. |
| `brier_score` | Brier | 0–1 | `(p − y)²`; menor es mejor. |
| `certainty_percent` | certeza | % | `(1 − Brier) × 100`; cercanía predicción–realidad. |
| `certainty_delta_vs_venezuela_2026` | delta | puntos % | Diferencia de certeza respecto a `venezuela_2026`. |
| `certainty_vs_venezuela_2026_percent` | similitud certeza | % | `100 − |delta|`; 100 = misma certeza que referencia. |

### 1.5 Verificación diaria (`DAILY_VERIFICATION_HEADERS`)

| Columna UI | Campo | Unidad | Descripción |
|---|---|---|---|
| `ventana` | tipo de fila | — | `Estimado ayer -> real hoy`, `Estimacion manana base`, `Estimacion manana ajustada`. |
| `fecha` | `verification_date` / fecha siguiente | fecha | Día verificado o día estimado. |
| `umbral_mw` | `threshold_mw` | Mw | Magnitud umbral de la verificación. |
| `probabilidad_estimada` | `predicted_probability` | 0–1 | Probabilidad predicha para ese día/umbral. |
| `valor_real` | `observed_binary` | 0/1 / `pendiente` | Resultado observado (1 = se alcanzó umbral). |
| `acierto` | `hit` | bool / `pendiente` | Coincidencia predicción–observación. |
| `brier` | `brier_score` | 0–1 | Error cuadrático de la probabilidad. |
| `error_abs` | `absolute_error` | 0–1 | \|p − y\|. |
| `ajuste_aplicado` | `adjustment_factor` | factor | Multiplicador aplicado al conteo Omori del día siguiente (rango típico 0.15–1.75). |

---

## 2. Pestaña Cálculo y Estimación Internacional

Modelo pseudo-prospectivo sobre catálogos **USGS**, **INGV** (Italia) y **SGC** (Colombia), con foco geográfico en Venezuela. Referencia anómala: ventana alrededor de **2026-06-26**.

### 2.1 Controles — Fase 1 (ventanas)

| Control UI | Parámetro | Rango | Descripción |
|---|---|---|---|
| Fecha de corte | `as_of_date` | fecha | Último día incluido en el análisis. |
| Lookback (días) | `lookback_days` | 120–3650 | Historia total consultada hacia atrás desde la fecha de corte. |
| Ventana (días) | `window_days` | 14–365 | Duración de cada ventana espacio-temporal de features. |
| Stride (días) | `stride_days` | 1–90 | Desplazamiento entre ventanas consecutivas. |
| Horizonte target (días) | `horizon_days` | 7–180 | Días hacia adelante para definir la etiqueta objetivo (¿ocurrió M ≥ umbral?). |
| Umbral clasificación M >= | `threshold_magnitude` | 3.5–8.5 | Etiqueta binaria principal (por defecto M ≥ 5.0). |
| Umbral alternativo M >= | `alternative_threshold_magnitude` | 3.5–7.0 | Segunda etiqueta (por defecto M ≥ 4.5) para evaluación dual. |
| Magnitud mínima catálogo | `min_magnitude` | 1.0–7.0 | Eventos por debajo se excluyen del catálogo. |
| Usar APIs live | `use_live_sources` | bool | Descarga catálogos en vivo; si falla, usa fixtures locales. |

### 2.2 Controles — Fase 1.1 (validación y calibración)

| Control UI | Parámetro | Rango | Descripción |
|---|---|---|---|
| Walk-forward min train | `walk_forward_min_train` | 4–30 ventanas | Mínimo de ventanas de entrenamiento por fold walk-forward. |
| Walk-forward test size | `walk_forward_test_size` | 1–12 ventanas | Ventanas de prueba por fold. |
| Walk-forward step | `walk_forward_step` | 1–15 ventanas | Avance temporal entre folds. |
| Calibración Platt | `use_platt_calibration` | bool | Ajusta probabilidades del clasificador logístico con scaling Platt. |
| Fracción calibración Platt | `platt_calibration_fraction` | 0.05–0.5 | Porción del train reservada para calibrar Platt. |
| Class weight | `use_class_weight` | bool | Balancea clases desbalanceadas en el clasificador. |
| InSAR/GNSS MIDAS medido (NGL) | `use_live_insar_gnss` | bool | Sustituye proxy InSAR por velocidades GNSS MIDAS (NGL IGS14). |

### 2.3 Tabla resumen por fuente

| Columna UI | Campo | Unidad | Descripción |
|---|---|---|---|
| `fuente` | `source` | — | `usgs`, `ingv`, `sgc`. |
| `pais` | `country` | — | País o región de la agencia. |
| `estado` | `status` | — | `ok`, `fallback`, `empty`, etc. |
| `eventos` | `event_count` | conteo | Número de eventos tras filtros de magnitud y bbox. |
| `inicio` | `start_date` | fecha | Primer evento en el lookback. |
| `fin` | `end_date` | fecha | Último evento antes de la fecha de corte. |

### 2.4 Variables por ventana (`FEATURE_ORDER`)

Últimas 12 ventanas mostradas en UI; el modelo usa el historial completo.

| Columna UI | Campo | Unidad | Descripción |
|---|---|---|---|
| `window_start` | inicio ventana | fecha | Primer día de la ventana de features. |
| `window_end` | fin ventana | fecha | Último día de la ventana de features. |
| `n_events` | conteo | eventos | Eventos sísmicos en la ventana. |
| `m_mean` | magnitud media | M | Promedio de magnitudes en la ventana. |
| `gr_b` | b-value | adimensional | Pendiente Gutenberg-Richter estimada en la ventana. |
| `gr_a` | a-value | adimensional | Intercepto Gutenberg-Richter (log₁₀ de tasa). |
| `benioff_rate` | tasa Benioff | energía/día | Σ 10^(0.75M + 2.4) / días de ventana; proxy de liberación energética. |
| `delta_m` | ΔM | M | M_observada_max − M_esperada_GR; positivo = más eventos grandes de lo esperado. |
| `mu_recurrence_days` | μ recurrencia | días | Intervalo medio entre eventos consecutivos en la ventana. |
| `eta_rms` | η RMS | adimensional | Error RMS del ajuste G-R (calidad del ajuste b). |
| `n_usgs` | conteo USGS | eventos | Eventos de USGS en la ventana. |
| `n_ingv` | conteo INGV | eventos | Eventos de INGV en la ventana. |
| `n_sgc` | conteo SGC | eventos | Eventos de SGC en la ventana. |
| `max_magnitude_in_window` | M máx | M | Mayor magnitud registrada en la ventana. |
| `benioff_accel` | aceleración Benioff | Δ tasa/día | Cambio de tasa Benioff entre mitades de la ventana. |
| `gr_b_delta` | Δb | adimensional | Diferencia de b-value entre primera y segunda mitad de ventana. |
| `event_rate_trend` | tendencia tasa | eventos/día² | Cambio de tasa de eventos entre mitades de ventana. |

### 2.5 InSAR/GNSS por ventana

| Columna UI | Campo | Unidad | Descripción |
|---|---|---|---|
| `window_start` | inicio | fecha | Inicio de ventana temporal. |
| `window_end` | fin | fecha | Fin de ventana temporal. |
| `vsr_mm_per_year` | VSR | mm/año | Tasa de desplazamiento **vertical** (InSAR/GNSS). |
| `ssr_mm_per_year` | SSR | mm/año | Tasa de desplazamiento **lateral** (plano horizontal). |
| `nsr_mm_per_year` | NSR | mm/año | Tasa neta √(VSR² + SSR²). |
| `data_status` | estado | enum | `measured`, `proxy_from_seismic_catalog`, `placeholder_pending_source`. |
| `notes` | notas | texto | Fuente y trazabilidad (p. ej. NGL MIDAS IGS14). |

### 2.6 Predicciones en ventanas de prueba

| Columna UI | Campo | Unidad | Descripción |
|---|---|---|---|
| `window_start` | inicio | fecha | Inicio de la ventana de features evaluada. |
| `window_end` | fin | fecha | Fin de la ventana de features. |
| `target_end` | fin horizonte | fecha | Fin del horizonte donde se observa la etiqueta real. |
| `target_cls_m5` | etiqueta M≥5 | 0/1 | 1 si hubo evento M ≥ 5.0 en el horizonte; 0 si no. |
| `pred_prob_m5` | P(M≥5) | 0–1 | Probabilidad predicha por clasificador (posible calibración Platt). |
| `target_cls_m45` | etiqueta M≥4.5 | 0/1 | Etiqueta alternativa M ≥ 4.5. |
| `pred_prob_m45` | P(M≥4.5) | 0–1 | Probabilidad predicha para umbral alternativo. |
| `target_exceedance` | excedencia real | 0–1 | Probabilidad empírica de excedencia G-R observada en horizonte. |
| `pred_exceedance_gr` | excedencia predicha | 0–1 | Predicción de excedencia vía modelo G-R. |
| `target_mmax` | Mmax real | M | Magnitud máxima observada en el horizonte. |
| `pred_mmax_gr` | Mmax predicha | M | Magnitud máxima estimada por cola Gutenberg-Richter. |

**Gráficas:** curva P(M≥umbral) vs ventanas; dispersión Mmax real vs predicha.

### 2.7 Métricas de evaluación (`metrics_table`)

| Métrica UI | Significado | Rango / interpretación |
|---|---|---|
| `F1` | F1-score clasificación M≥5 (holdout) | 0–1; mayor es mejor. |
| `GM` | Geometric mean de sensibilidad y especificidad | 0–1. |
| `PRC AUC` | Área bajo curva precision-recall | 0–1; útil con clases desbalanceadas. |
| `Molchan alarm fraction` | Fracción de tiempo en alarma (Molchan) | 0–1; costo de falsas alarmas. |
| `Molchan missed fraction` | Fracción de eventos no detectados | 0–1; costo de fallos. |
| `L-test log-likelihood` | Log-verosimilitud del modelo probabilístico | mayor suele ser mejor. |
| `F1 walk-forward avg` | F1 promedio en validación walk-forward | estimación más conservadora que holdout. |
| `PRC AUC walk-forward avg` | PRC AUC promedio walk-forward | robustez temporal. |
| `F1 M>=4.5 holdout` | F1 con umbral alternativo M ≥ 4.5 | sensibilidad a eventos moderados. |
| `Operational threshold M>=5` | Umbral operativo de probabilidad para M≥5 | probabilidad que iguala precision y recall en train. |
| `Operational threshold M>=4.5` | Umbral operativo para M≥4.5 | idem para etiqueta alternativa. |
| `MSE exceedance GR` | Error cuadrático medio en excedencia G-R | menor es mejor. |
| `MSE Mmax GR-tail` | MSE de Mmax vía cola G-R | menor es mejor. |
| `MAE Mmax GR-tail` | Error absoluto medio de Mmax | menor es mejor. |
| `R2 Mmax GR-tail` | Coeficiente de determinación R² de Mmax | 0–1; ajuste de regresión. |
| `S-test spatial skill` | Habilidad espacial del modelo de Mmax | métrica de skill espacial. |

### 2.8 Similitud con ventana anómala

| Columna UI | Campo | Unidad | Descripción |
|---|---|---|---|
| `window_start` | inicio | fecha | Inicio de ventana de prueba. |
| `window_end` | fin | fecha | Fin de ventana de prueba. |
| `target_end` | fin horizonte | fecha | Fin del horizonte objetivo. |
| `similarity_to_anomaly` | similitud coseno | −1 a 1 | Similitud del vector de features (normalizado) respecto a la ventana de referencia **2026-06-26**. 1 = patrón idéntico. |

### 2.9 Importancia de variables y ablación

| Columna UI | Campo | Unidad | Descripción |
|---|---|---|---|
| `feature` | nombre variable | — | Variable de `FEATURE_ORDER`. |
| `score` | coeficiente / importancia | adimensional | Magnitud del coeficiente del clasificador o regresor. |
| `importance_percent` | % relativo | % | Contribución relativa al modelo. |
| `performance_drop` | caída rendimiento | 0–1 | Pérdida de F1/R² al eliminar la variable (ablación). |

---

## 3. Pestaña Análisis comparativo (Fases 1–5)

Comparación multi-caso sobre `case_library/`. Botón **Actualizar gráficas** refresca todas las salidas.

### 3.1 Controles

| Control UI | Campo | Opciones / rango | Descripción |
|---|---|---|---|
| Casos comparativos | `selected_cases` | multiselect `case_id` | Filtra gráficos y tablas. |
| Métrica para barras | `bar_metric` | 11 métricas (§3.2) | Eje Y del gráfico de barras. |
| Eje X (dispersión) | `x_metric` | 11 métricas | Eje X del scatter. |
| Eje Y (dispersión) | `y_metric` | 11 métricas | Eje Y del scatter. |
| Horizonte post-evento (días) | `horizon_days` | 1–365 | Ventana para probabilidad de magnitud similar. |
| Filtro contexto geológico | `geology_context_filter` | 7 tipos + todos | Filtra tabla/gráfica geológica. |
| Filtro placa tectónica | `tectonic_plate_filter` | placas únicas + todas | Filtra tabla de fallas. |
| Filtro Fase 5 por dominio | `phase5_domain_filter` | dominios + todos | Filtra catálogo de modelos recomendados. |

### 3.2 Métricas comparativas (barras y dispersión)

| Etiqueta UI | Ruta en `event.yaml` | Unidad | Descripción |
|---|---|---|---|
| Magnitud Mw | `magnitude_mw` | Mw | Magnitud de momento; proxy de energía y tamaño de ruptura. |
| Profundidad (km) | `depth_km` | km | Profundidad del foco; afecta atenuación y mecanismo. |
| Distancia a ciudades (km) | `distance_to_cities_km` | km | Distancia mínima a centros urbanos; proxy de exposición. |
| Réplicas (conteo) | `advanced_features.seismic.aftershock_count` | eventos | Tamaño de la secuencia post-mainshock. |
| Omori p-value | `advanced_features.seismic.omori_decay_p` | adimensional | Exponente p de Omori-Utsu; mayor p → decaimiento más rápido. |
| b-value Gutenberg-Richter | `advanced_features.seismic.gutenberg_richter_b_value` | adimensional | Pendiente G-R; b bajo implica más eventos grandes relativos. |
| Slip rate (mm/año) | `advanced_features.seismic.estimated_slip_rate_mm_per_year` | mm/año | Tasa de deslizamiento en falla cercana. |
| PGA (g) | `advanced_features.seismic.pga_g` | g | Aceleración máxima en suelo (valor agregado por caso). |
| Vs30 (m/s) | `advanced_features.geological_geotechnical.vs30_m_per_s` | m/s | Velocidad onda S en 30 m; clasificación de sitio NEHRP. |
| Lluvia 30d (mm) | `advanced_features.climatic.rainfall_30d_mm` | mm | Acumulado pluviométrico 30 días previos. |
| Población expuesta | `advanced_features.human_urban.exposed_population` | personas | Población en área afectada potencial. |

### 3.3 Probabilidad de magnitud similar

| Columna UI | Campo | Unidad | Descripción |
|---|---|---|---|
| `case_id` | `case_id` | — | Caso comparativo. |
| `n_eventos_horizonte` | conteo | eventos | Picos de magnitud documentados dentro del horizonte. |
| `n_similares` | conteo | eventos | Eventos con magnitud similar a la de referencia (±ΔM). |
| `%` | probabilidad | % | Porcentaje empírico de similitud. |

**Gráfica:** barras de % por `case_id`, ordenadas descendente.

### 3.4 Modelo de riesgo compuesto (Fase 4)

| Columna UI | Campo | Unidad | Descripción |
|---|---|---|---|
| `case_id` | `case_id` | — | Caso evaluado. |
| `risk_score_total` | `risk_model_outputs.risk_score_total` | 0–100 | Puntaje compuesto de riesgo territorial. |
| `risk_category` | `risk_model_outputs.risk_category` | enum | `riesgo_bajo`, `riesgo_medio`, `riesgo_alto`, `riesgo_critico`. |

**Componentes internos** (no mostrados directamente en tabla, alimentan el score):

| Componente | Campo | Descripción |
|---|---|---|
| Amenaza sísmica | `component_scores.seismic_hazard` | Energía, réplicas, densidad. |
| Exposición humana | `component_scores.human_exposure` | Población y densidad urbana. |
| Vulnerabilidad estructural | `component_scores.structural_vulnerability` | Tipología constructiva. |
| Vulnerabilidad geotécnica | `component_scores.geotechnical_vulnerability` | Suelo, pendiente, licuefacción. |
| Condiciones climáticas | `component_scores.climatic_conditions` | Lluvia, saturación. |
| Criticidad infraestructura | `component_scores.infrastructure_criticality` | Servicios críticos. |

### 3.5 Contexto geológico de localización

| Columna UI | Campo | Unidad | Descripción |
|---|---|---|---|
| `case_id` | `case_id` | — | Caso comparativo. |
| `tipo_contexto_geologico` | inferido en UI | enum | Clasificación automática del texto de contexto (§6). |
| `location_geology_context` | `advanced_features.geological_geotechnical.location_geology_context` | texto | Descripción libre del entorno geológico. |
| `vs30_m_per_s` | `vs30_m_per_s` | m/s | Velocidad de sitio; suelos blandos amplifican. |
| `litologia` | `lithology` | texto | Tipo de roca/suelo predominante. |
| `risk_category` | `risk_category` | enum | Categoría de riesgo del caso (Fase 4). |

### 3.6 Fallas geológicas, placas y eventos vinculados

| Columna UI | Campo | Unidad | Descripción |
|---|---|---|---|
| `case_id` | `case_id` | — | Caso comparativo. |
| `nearby_geological_faults` | array → texto | — | Fallas activas o sistémicas cercanas (lista unida). |
| `nearby_tectonic_plates` | array → texto | — | Placas tectónicas en interacción. |
| `faults_average_seismic_activity_events_per_year` | tasa | eventos/año | Sismicidad media histórica en fallas cercanas. |
| `fault_linked_relevant_events_count` | conteo | eventos | Número de eventos históricos vinculados a fallas. |
| `fault_linked_relevant_events_summary` | resumen | texto | Lista compacta: nombre, año, Mw, falla. |

### 3.7 Catálogo Fase 5

| Columna UI | Campo | Unidad | Descripción |
|---|---|---|---|
| `dominio` | dominio | — | `sismicidad`, `riesgo_territorial`, `incertidumbre`. |
| `modelo_recomendado` | nombre modelo | — | Modelo sugerido para ese dominio (p. ej. ETAS, XGBoost, FCN geoespacial). |
| `n_modelos_en_dominio` | conteo | — | Total de modelos listados en ese dominio. |

**Fuente:** `models/recommended_models_phase5.yaml`.

### 3.8 Análisis PGA

#### Resumen por caso

| Columna UI | Campo | Unidad | Descripción |
|---|---|---|---|
| `case_id` | `case_id` | — | Caso comparativo. |
| `pga_g` | `advanced_features.seismic.pga_g` | g | PGA agregada del caso. |
| `mmi_intensity` | `advanced_features.seismic.mmi_intensity` | escala MMI | Intensidad modificada de Mercalli (si disponible). |
| `station_estimates_count` | conteo | — | Número de estimaciones por estación/zona. |
| `pga_measurement_quality` | calidad | enum | `instrumented`, `estimated_indirect`, `unknown`, etc. |

#### Detalle por estación/zona

| Columna UI | Campo | Unidad | Descripción |
|---|---|---|---|
| `case_id` | `case_id` | — | Caso al que pertenece la estimación. |
| `location` | `location` | texto | Zona o estación (p. ej. Los Palos Grandes). |
| `pga_g` | `pga_g` | g | PGA puntual estimada o medida. |
| `pga_g_min` | `pga_g_min` | g | Límite inferior del rango de incertidumbre. |
| `pga_g_max` | `pga_g_max` | g | Límite superior del rango. |
| `site_class` | `site_class` | NEHRP | Clase de sitio (roca, aluvial, etc.). |
| `estimate_method` | `estimate_method` | texto | Método (acelerógrafo, daño estructural, sismoscopio…). |
| `source` | `source` | texto | Referencia bibliográfica o agencia. |
| `notes` | `notes` | texto | Advertencias metodológicas. |

**Avisos dinámicos en UI:**

- **Advertencia sesgo PGA:** aparece si `pga_measurement_quality = estimated_indirect` (p. ej. `venezuela_1967` NAS).
- **Catálogos internacionales 2026:** verificación USGS/GFZ/EMSC al seleccionar `venezuela_2026`.

---

## 4. Pestaña Capa A — Tectónica Principal

Datos aislados en `layer_a_tectonic/`. No se mezclan con `event_cases/` ni `case_library/`.

### 4.1 Controles

| Control UI | Parámetro | Descripción |
|---|---|---|
| Usar fixtures sintéticos si no hay raw/ | `use_fixtures` | Carga datos de prueba si no existen catálogos en `data/raw/`. |
| Descargar catálogo USGS a data/raw/ | `download_usgs` | Descarga catálogo USGS antes de ejecutar (INGV/SGC según pipeline). |

### 4.2 Resumen (`pipeline_summary.json`)

| Campo | Unidad | Descripción |
|---|---|---|
| `layer` | — | Siempre `A_tectonic`. |
| `usgs_download_status` | estado | Resultado de descarga USGS. |
| `ingv_download_status` | estado | Resultado de descarga INGV. |
| `sgc_download_status` | estado | Resultado de descarga SGC. |
| `events_normalized` | conteo | Eventos tras normalización. |
| `events_deduplicated` | conteo | Eventos tras deduplicación inter-fuente. |
| `events_with_faults` | conteo | Eventos con falla más cercana asignada. |
| `aftershock_sequences` | conteo | Secuencias de réplicas identificadas. |
| `doublet_candidates` | conteo | Pares candidatos a doblete. |
| `mainshock_id` | ID | Evento principal del reporte Venezuela 2026-06-24. |
| `outputs` | rutas | Archivos parquet/geojson generados. |
| `persistence` | metadatos | Run ID y rutas en `layer_a_tectonic/persistence/`. |

### 4.3 Catálogo con fallas (`catalog_with_faults`)

| Columna UI | Campo | Unidad | Descripción |
|---|---|---|---|
| `event_id` | `event_id` | — | Identificador único del evento. |
| `source` | `source` | — | Fuente del catálogo (`usgs`, `ingv`, `sgc`). |
| `datetime_utc` | `datetime_utc` | ISO 8601 | Fecha y hora UTC del evento. |
| `magnitude` | `magnitude` | M | Magnitud preferida del catálogo. |
| `magnitude_class` | `magnitude_class` | enum | Clasificación por magnitud (§6). |
| `depth_km` | `depth_km` | km | Profundidad del hipocentro. |
| `depth_class` | `depth_class` | enum | Clasificación por profundidad (§6). |
| `nearest_fault_name` | `nearest_fault_name` | texto | Nombre de la falla GEM/USGS más cercana. |
| `distance_to_nearest_fault_km` | `distance_to_nearest_fault_km` | km | Distancia al segmento de falla más próximo. |

### 4.4 Dobletes (`doublet_candidates`)

| Columna UI | Campo | Unidad | Descripción |
|---|---|---|---|
| `doublet_id` | `doublet_id` | — | Identificador del par candidato. |
| `event_id_1` | `event_id_1` | — | Primer evento del par. |
| `event_id_2` | `event_id_2` | — | Segundo evento del par. |
| `classification` | `classification` | enum | `high_confidence_doublet`, `possible_doublet`, `catalog_uncertainty`. |
| `time_delta_seconds` | `time_delta_seconds` | s | Separación temporal entre eventos. |
| `distance_km` | `distance_km` | km | Separación espacial (haversine). |
| `confidence_level` | `confidence_level` | A/B | A = alta confianza; B = posible doblete. |

---

## 5. Pestaña Capa B — Geofísica Ambiental

Datos aislados en `layer_b_geophysical/`. Análisis **correlacional y exploratorio** — no implica causalidad sísmica directa.

### 5.1 Controles

| Control UI | Parámetro | Descripción |
|---|---|---|
| Generar/usar series sintéticas si no hay raw/ | `use_synthetic` | Usa o genera series ambientales sintéticas si faltan datos reales. |

### 5.2 Resumen (`pipeline_summary.json`)

| Campo | Unidad | Descripción |
|---|---|---|
| `layer` | — | Siempre `B_geophysical`. |
| `primary_region` | código | Región principal analizada (p. ej. `venezuela_caribe`). |
| `reference_datetime_utc` | ISO 8601 | Instante de referencia del análisis. |
| `observations_normalized` | conteo | Observaciones ambientales normalizadas. |
| `features_computed` | conteo | Features derivadas calculadas. |
| `correlations` | conteo | Pares correlacionados evaluados. |
| `international_comparisons` | conteo | Comparaciones con regiones de referencia. |
| `cluster_assignments` | conteo | Asignaciones de clustering temporal. |
| `environmental_anomaly_index` | 0–100 | Índice compuesto de anomalía ambiental. |

### 5.3 Features ambientales (`environmental_features`)

| Columna UI | Campo | Unidad | Descripción |
|---|---|---|---|
| `region_code` | `region_code` | — | Código de región (`venezuela_caribe`, etc.). |
| `feature_name` | `feature_name` | — | Nombre de la variable derivada (ver tabla inferior). |
| `feature_value` | `feature_value` | variable | Valor numérico de la feature. |
| `window_days` | `window_days` | días | Ventana temporal usada (negativo = días hacia atrás). |
| `evidence_level` | `evidence_level` | A/B/C | Calidad estadística del dato (§6). |

**Nombres de `feature_name` generados por el pipeline:**

| Grupo | Nombres | Descripción breve |
|---|---|---|
| SST | `sst_mean_7d`, `sst_mean_30d`, `sst_std_7d`, `sst_delta_7d`, `sst_delta_30d`, `sst_anomaly` | Temperatura superficial del mar y anomalías. |
| Presión | `pressure_mean_7d`, `pressure_std_7d`, `pressure_change_24h`, `pressure_change_72h`, `pressure_anomaly` | Presión atmosférica y cambios recientes. |
| Lluvia | `rain_acc_1d`, `rain_acc_3d`, `rain_acc_7d`, `rain_acc_15d`, `rain_acc_30d` | Acumulados pluviométricos. |
| Humedad suelo | `soil_moisture_mean`, `soil_moisture_std`, `soil_moisture_anomaly`, `soil_moisture_trend` | Humedad del suelo y tendencia. |
| Mareas | `earth_tide_mean`, `earth_tide_max`, `earth_tide_gradient`, `earth_tide_stress_index` | Carga de marea y índice de estrés asociado. |

### 5.4 Índices ambientales (`environmental_indexes`)

| Columna UI | Campo | Unidad | Descripción |
|---|---|---|---|
| `region_code` | `region_code` | — | Región evaluada. |
| `environmental_anomaly_index` | índice compuesto | 0–100 | Promedio de componentes; mayor = mayor anomalía ambiental. |
| `sst_activity_index` | componente SST | 0–100 | Actividad/anomalía de temperatura marina. |
| `rainfall_stress_index` | componente lluvia | 0–100 | Estrés pluviométrico reciente (`rain_acc_7d` escalado). |
| `soil_saturation_index` | componente suelo | 0–100 | Saturación de suelo (`soil_moisture_mean` escalado). |

Los índices componentes adicionales (presión, océano) contribuyen al compuesto pero no tienen columna propia en la tabla UI.

### 5.5 Comparación internacional (`international_comparison`)

| Columna UI | Campo | Unidad | Descripción |
|---|---|---|---|
| `region_code` | `region_code` | — | Región analizada. |
| `reference_region` | `reference_region` | — | Región de referencia para comparar (p. ej. `chile_subduction`). |
| `similarity_score` | `similarity_score` | 0–100 | Similitud del perfil ambiental respecto a la referencia. |
| `evidence_level` | `evidence_level` | A/B/C | Confianza estadística de la comparación. |

---

## 6. Valores categóricos y enums

### 6.1 Categorías de riesgo (`risk_category`)

| Valor | Significado |
|---|---|
| `riesgo_bajo` | Puntaje compuesto bajo; exposición y vulnerabilidad limitadas. |
| `riesgo_medio` | Riesgo moderado; requiere monitoreo. |
| `riesgo_alto` | Riesgo elevado; múltiples componentes altos. |
| `riesgo_critico` | Riesgo extremo; eventos de gran magnitud con alta exposición. |

### 6.2 Tipos de contexto geológico (inferidos en UI)

| Clave interna | Etiqueta UI | Criterio |
|---|---|---|
| `margen_subduccion` | Margen de subducción | Texto con subducción, megathrust. |
| `falla_deslizamiento` | Falla de deslizamiento / transformante | transformante, strike-slip, fallas activas. |
| `cuenca_lacustre` | Cuenca lacustre | lacustre, lago. |
| `cuenca_sedimentaria` | Cuenca sedimentaria / aluvial | cuenca, sediment, aluvial, relleno. |
| `intermontano` | Valle intermontano | intermontano, valles. |
| `costero` | Entorno costero | costa, planicies costeras. |
| `otro` | Otro contexto | Resto de descripciones. |

### 6.3 Clase de magnitud (Capa A)

| Valor | Rango M |
|---|---|
| `micro` | M < 3.0 |
| `minor` | 3.0 ≤ M < 4.0 |
| `light` | 4.0 ≤ M < 5.0 |
| `moderate` | 5.0 ≤ M < 6.0 |
| `strong` | 6.0 ≤ M < 7.0 |
| `major` | 7.0 ≤ M < 8.0 |
| `great` | M ≥ 8.0 |

### 6.4 Clase de profundidad (Capa A)

| Valor | Rango (km) |
|---|---|
| `shallow_critical` | ≤ 10 |
| `shallow_crustal` | 10 < d ≤ 30 |
| `intermediate_shallow` | 30 < d ≤ 70 |
| `intermediate` | 70 < d ≤ 300 |
| `deep` | > 300 |

### 6.5 Clasificación de dobletes (Capa A)

| Valor | Significado |
|---|---|
| `high_confidence_doublet` | Par muy cercano en tiempo, espacio y magnitud (umbrales estrictos). |
| `possible_doublet` | Par dentro de umbrales amplios; requiere revisión. |
| `catalog_uncertainty` | No clasificado como doblete. |

### 6.6 Estado InSAR/GNSS

| Valor | Significado |
|---|---|
| `measured` | Dato instrumentado (GNSS MIDAS NGL u otra fuente medida). |
| `proxy_from_seismic_catalog` | Proxy derivado del catálogo sísmico (benioff, delta_m, etc.). |
| `placeholder_pending_source` | Sin dato; pendiente de integración. |

### 6.7 Nivel de evidencia (Capa B)

| Valor | Criterio típico |
|---|---|
| `A` | p < 0.01 y n ≥ 30 (correlación fuerte). |
| `B` | p < 0.05 o correlación moderada. |
| `C` | p ≥ 0.05, n < 10, o dato sintético/exploratorio. |

### 6.8 Calidad de medición PGA

| Valor | Significado |
|---|---|
| `instrumented` | Medición directa con acelerógrafo o red moderna. |
| `estimated_indirect` | Estimación post-evento (daño, intensidad, sismoscopio). **No usar para calibración forward.** |
| `unknown` | Calidad no documentada. |

---

## 7. Campos fuera de la UI (relacionados)

Estos campos **no tienen pestaña propia** en el dashboard pero alimentan modelos referenciados en la documentación:

| Salida | Ubicación | Campos principales |
|---|---|---|
| FCN geológico | `storage/geological_model/outputs/latest.json` | `geotechnical_vulnerability`, `liquefaction_probability`, `spatial_amplification_factor`, `fault_coupling_index`, `structural_damage_probability`, `landslide_probability`, `risk_category`, `insar_bridge` |
| JSON internacional | `storage/venezuela/international/.../international_estimation_*.json` | Mismo contenido que la pestaña internacional + metadatos de persistencia |
| Proyección CLI | `docs/venezuela_projection_<fecha>.json` | Blend bayesiano Omori/G-R a horizontes 30/45 d |

Ver `docs/ui_features_and_theory.md` §11 y `docs/foco-geologico.md` para el diccionario completo del modelo FCN.

---

## Referencias cruzadas

| Tema | Documento |
|---|---|
| Ecuaciones Omori, G-R, certeza hindcast | `docs/ui_features_and_theory.md` §8 |
| Inventario Fase 3 (42 campos schema) | `docs/ui_features_and_theory.md` §9 |
| Modelo FCN e InSAR | `docs/ui_features_and_theory.md` §11, `docs/foco-geologico.md` |
| Comandos `make` | `README.md`, `docs/data-earthquake-analysis.txt` |

---

*Actualizar este diccionario cuando cambien headers de tablas Gradio, `FEATURE_ORDER`, schemas o nuevas pestañas en `scripts/comparative_charts.py`.*
