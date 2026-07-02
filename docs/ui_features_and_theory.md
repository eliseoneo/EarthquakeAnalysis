# EarthquakeAnalysis — Features de la UI, valores y marco teórico

Documento de referencia para el dashboard comparativo (`scripts/comparative_charts.py`).

- **Fuente de datos:** `case_library/*/event.yaml` (10 casos comparativos).
- **Catálogo Fase 5:** `models/recommended_models_phase5.yaml`.
- **Modelo geológico (FCN):** `models/geological_geospatial_fcn.yaml`, paquete `geological_model/`.
- **Proveedores InSAR/GNSS:** `models/insar_gnss_providers.yaml`.
- **Marco teórico geológico:** `docs/foco-geologico.md`.
- **Scripts relacionados (fuera de UI):**
  - `scripts/project_venezuela_probabilities.py` → `docs/venezuela_projection_<fecha>.json`
  - `scripts/run_international_estimation.py` → `storage/venezuela/international/.../international_estimation_*.json`
  - `scripts/run_geological_model.py` → `storage/geological_model/outputs/latest.json`
  - `scripts/fetch_insar_gnss.py` → actualiza filas InSAR/GNSS medidas y el JSON internacional

---

## 1. Controles de la interfaz

| Control UI | Tipo | Valor por defecto | Rango / opciones | Rol |
|---|---|---|---|---|
| Casos comparativos | Dropdown multiselect | Primeros 5 `case_id` | 10 casos de `case_library` | Filtra todos los gráficos y tablas |
| Métrica para barras | Dropdown | `Magnitud Mw` | 10 métricas (ver §2) | Eje Y de barras comparativas |
| Eje X (dispersión) | Dropdown | `Magnitud Mw` | 10 métricas | Eje X del scatter |
| Eje Y (dispersión) | Dropdown | `Replicas (conteo)` | 10 métricas | Eje Y del scatter |
| Horizonte post-evento (días) | Slider | **30** | 1–365 | Ventana para probabilidad de magnitud similar |
| Filtro contexto geológico | Dropdown | `Todos los tipos` | 7 tipos inferidos | Filtra tabla/gráfica geológica |
| Filtro placa tectónica | Dropdown | `Todas las placas` | Placas únicas del dataset | Filtra tabla/gráfica de fallas |
| Filtro Fase 5 por dominio | Dropdown | `Todos los dominios` | `sismicidad`, `riesgo_territorial`, `incertidumbre` | Filtra catálogo de modelos |
| Fecha de corte | Textbox | **hoy (YYYY-MM-DD)** | fecha válida | Inicio de la ventana forward (monitoreo en tiempo real) |
| Escenario de calibración | Dropdown | **Base (calibración YAML)** | `base`, `conservador`, `optimista` | Ajuste de K y b según magnitudes observadas |
| Días forward | Slider | **8** | 1–120 | Próximos N días **desde la fecha de corte** (no desde mainshock) |
| Días validación histórica | Slider | **8** | 1–120 | Ventana retrospectiva para medir certeza (%) del modelo contra eventos observados |
| Magnitud objetivo (Mw) | Number | **6.0** | 4.0–9.5 | Umbral para probabilidad proyectada |

---

## 2. Métricas comparativas (barras y dispersión)

Cada métrica se lee de `case_library/*/event.yaml` mediante la ruta indicada.

| Etiqueta UI | Campo en datos | Unidad | Marco teórico |
|---|---|---|---|
| Magnitud Mw | `magnitude_mw` | adimensional (Mw) | Escala de magnitud de momento; proxy de energía liberada y tamaño de ruptura. |
| Profundidad (km) | `depth_km` | km | Profundidad del foco; controla atenuación, mecanismo y riesgo de tsunamis/licuefacción. |
| Distancia a ciudades (km) | `distance_to_cities_km` | km | Proxy de exposición espacial: a menor distancia, mayor sacudida percibida y daño urbano potencial. |
| Réplicas (conteo) | `advanced_features.seismic.aftershock_count` | eventos | Tamaño de la secuencia post-mainshock; insumo para leyes de decaimiento (Omori-Utsu, ETAS). |
| Omori p-value | `advanced_features.seismic.omori_decay_p` | adimensional | Exponente **p** de Omori-Utsu: \( n(t) \propto (t+c)^{-p} \); describe velocidad de decaimiento de réplicas. |
| b-value Gutenberg-Richter | `advanced_features.seismic.gutenberg_richter_b_value` | adimensional | Pendiente de la ley G-R: \( \log_{10} N = a - bM \); bajo b ⇒ más eventos grandes relativos. |
| Slip rate (mm/año) | `advanced_features.seismic.estimated_slip_rate_mm_per_year` | mm/año | Tasa de deslizamiento en falla; relacionada con acumulación de deformación y sismicidad a largo plazo. |
| PGA (g) | `advanced_features.seismic.pga_g` | g | Aceleración máxima en suelo; comparativa en UI (p. ej. `venezuela_1967` NAS). |
| Vs30 (m/s) | `advanced_features.geological_geotechnical.vs30_m_per_s` | m/s | Velocidad de onda S en los primeros 30 m; proxy NEHRP de amplificación sísmica local. |
| Lluvia 30d (mm) | `advanced_features.climatic.rainfall_30d_mm` | mm | Antecedente pluviométrico; incrementa saturación y riesgo de remoción en masa post-sismo. |
| Población expuesta | `advanced_features.human_urban.exposed_population` | personas | Exposición demográfica en el área afectada; componente clave del riesgo compuesto. |

### Valores por caso (métricas UI)

| case_id | Mw | Prof. (km) | Dist. ciudades | Réplicas | Omori p | b-value | Slip (mm/a) | Vs30 | Lluvia 30d | Población |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| california_doublets | 6.5 | 10.0 | 20.0 | 40 | 1.0 | 0.9 | 25.0 | 360 | 60 | 1500000 |
| chile_2010 | 8.8 | 35.0 | 25.0 | 200 | 1.0 | 0.85 | 65.0 | 400 | 130 | 2000000 |
| ecuador_2016 | 7.8 | 20.0 | 28.0 | 150 | 1.0 | 0.88 | 55.0 | 310 | 180 | 900000 |
| haiti_2010 | 7.0 | 13.0 | 15.0 | 60 | 1.05 | 0.95 | 7.0 | 250 | 90 | 2500000 |
| japan_2011 | 9.0 | 29.0 | 130.0 | 500 | 0.95 | 0.82 | 80.0 | 280 | 120 | 5000000 |
| mexico_2017 | 7.1 | 51.0 | 120.0 | 30 | 1.1 | 0.93 | 50.0 | 200 | 100 | 9000000 |
| turkey_syria_2023 | 7.8 | 18.0 | 30.0 | 200 | 1.0 | 0.9 | 9.0 | 340 | 70 | 3500000 |
| venezuela_1812 | 7.0 | 20.0 | 10.0 | 0 | 1.0 | 0.9 | 6.0 | 280 | 0 | 80000 |
| venezuela_1967 | 6.6 | 23.0 | 32.0 | 28 | 1.0 | 0.92 | 8.0 | 290 | 110 | 1200000 |
| venezuela_2026 | 7.5 | 10.0 | 300.0 | 130 | 1.0 | 0.9 | 8.0 | 300 | 145 | 2200000 |

> Nota: valores numéricos tomados de `case_library/*/event.yaml` al momento de generar este documento.

---

## 3. Probabilidad de magnitud similar (horizonte post-evento)

### Salidas UI

| Elemento | Columnas / eje | Descripción |
|---|---|---|
| Gráfica de barras | `%` por `case_id` | Probabilidad empírica de eventos similares en el horizonte |
| Tabla resumen | `case_id`, `n_eventos_horizonte`, `n_similares`, `%` | Conteos y porcentaje ordenado descendente |

### Campos de datos

- `similar_magnitude_probability_dates.main_event_date`
- `similar_magnitude_probability_dates.reference_magnitude_mw`
- `similar_magnitude_probability_dates.magnitude_similarity_delta_mw`
- `similar_magnitude_probability_dates.highest_magnitude_events[]` con `event_date`, `days_after_main`, `magnitude_mw`

### Marco teórico

Análisis **empírico-frecuentista** sobre picos de magnitud documentados:

\[
P_{\text{similar}} = \frac{n_{\text{similares}}}{n_{\text{horizonte}}} \times 100
\]

donde un evento es *similar* si:

\[
|M_i - M_{\text{ref}}| \leq \Delta M
\]

y \( \text{days\_after\_main}_i \leq H \) (horizonte en días seleccionado en UI).

Relacionado con modelos de Fase 5: **ETAS**, **Hawkes processes**, **spatio-temporal clustering** (para extensión espacio-temporal futura).

---

## 4. Modelo de riesgo compuesto (Fase 4)

### Salidas UI

| Elemento | Campos | Descripción |
|---|---|---|
| Barras `risk_score_total` | score 0–100 | Puntaje compuesto por caso |
| Distribución `risk_category` | conteo por categoría | Frecuencia de `riesgo_bajo` … `riesgo_critico` |
| Tabla resumen | `case_id`, `risk_score_total`, `risk_category` | Ranking de riesgo |

### Categorías permitidas

- `riesgo_bajo`
- `riesgo_medio`
- `riesgo_alto`
- `riesgo_critico`

### Valores por caso

| case_id | risk_score_total | risk_category |
|---|---:|---|
| california_doublets | 54.2 | riesgo_medio |
| chile_2010 | 88.1 | riesgo_critico |
| ecuador_2016 | 76.4 | riesgo_alto |
| haiti_2010 | 90.3 | riesgo_critico |
| japan_2011 | 92.0 | riesgo_critico |
| mexico_2017 | 74.8 | riesgo_alto |
| turkey_syria_2023 | 91.2 | riesgo_critico |
| venezuela_1812 | 71.0 | riesgo_alto |
| venezuela_1967 | 81.2 | riesgo_alto |
| venezuela_2026 | 79.4 | riesgo_alto |

### Marco teórico

**Ensemble jerárquico** con componentes normalizados (0–1):

| Componente | Campo | Interpretación |
|---|---|---|
| Amenaza sísmica | `component_scores.seismic_hazard` | Energía, réplicas, densidad local |
| Exposición humana | `component_scores.human_exposure` | Población y densidad urbana |
| Vulnerabilidad estructural | `component_scores.structural_vulnerability` | Tipología y antigüedad constructiva |
| Vulnerabilidad geotécnica | `component_scores.geotechnical_vulnerability` | Suelo, pendiente, licuefacción |
| Condiciones climáticas | `component_scores.climatic_conditions` | Lluvia, saturación, remoción en masa |
| Criticidad infraestructura | `component_scores.infrastructure_criticality` | Hospitales, vías, servicios críticos |

Salidas probabilísticas (`derived_outputs`):

- `probability_strong_aftershock`
- `probability_structural_damage`
- `probability_landslide`
- `population_exposure_index`
- `relative_urban_collapse_index`

Modelos Fase 5 relacionados: **XGBoost/LightGBM**, **Random Forest**, **Bayesian networks**, **GNN**, **Gaussian Processes**, **PySAL**, **FCN geoespacial geológico** (ver §11).

---

## 5. Contexto geológico de localización

### Salidas UI

| Elemento | Campos |
|---|---|
| Gráfica distribución | conteo por `tipo_contexto_geologico` |
| Tabla temática | `case_id`, `tipo_contexto_geologico`, `location_geology_context`, `vs30_m_per_s`, `litologia`, `risk_category` |

### Tipos inferidos en UI

| Clave interna | Etiqueta UI | Criterio de clasificación |
|---|---|---|
| `margen_subduccion` | Margen de subducción | palabras: subducción, megathrust |
| `falla_deslizamiento` | Falla de deslizamiento / transformante | transformante, strike-slip, fallas activas |
| `cuenca_lacustre` | Cuenca lacustre | lacustre |
| `cuenca_sedimentaria` | Cuenca sedimentaria / aluvial | cuenca, sediment, aluvial, relleno |
| `intermontano` | Valle intermontano | intermontano, valles |
| `costero` | Entorno costero | costa, planicies costeras |
| `otro` | Otro contexto | resto |

### Clasificación actual de casos

| case_id | tipo_contexto_geologico |
|---|---|
| chile_2010, ecuador_2016, japan_2011 | margen_subduccion |
| california_doublets, haiti_2010, turkey_syria_2023, venezuela_1967, venezuela_2026 | falla_deslizamiento |
| mexico_2017 | cuenca_lacustre |
| venezuela_1812 | intermontano |

### Marco teórico

- **Vs30:** clasificación de sitio sísmico (NEHRP); suelos blandos amplifican periodos largos.
- **Litología y cuenca sedimentaria:** controlan resonancia, licuefacción y asentamientos diferenciales.
- **Contexto geológico:** integra morfología, basamento y proximidad a estructuras activas para interpretar daño diferencial urbano.

---

## 6. Fallas geológicas, placas y eventos vinculados

### Salidas UI

| Elemento | Campos |
|---|---|
| Gráfica actividad | `faults_average_seismic_activity_events_per_year` por caso |
| Tabla temática | `nearby_geological_faults`, `nearby_tectonic_plates`, actividad promedio, conteo y resumen de eventos vinculados |

### Features en datos (Fase 3)

| Campo | Tipo | Descripción |
|---|---|---|
| `nearby_geological_faults` | array[string] | Fallas activas o sistémicas cercanas |
| `nearby_tectonic_plates` | array[string] | Placas en interacción |
| `faults_average_seismic_activity_events_per_year` | number | Tasa media histórica en fallas cercanas |
| `fault_linked_relevant_events` | array[object] | Eventos históricos ligados a falla (`event_name`, `event_year`, `magnitude_mw`, `linked_fault`) |

### Valores de actividad promedio por caso

| case_id | eventos/año |
|---|---:|
| california_doublets | 4.6 |
| chile_2010 | 2.4 |
| ecuador_2016 | 1.8 |
| haiti_2010 | 1.1 |
| japan_2011 | 3.1 |
| mexico_2017 | 2.2 |
| turkey_syria_2023 | 2.9 |
| venezuela_1812 | 1.3 |
| venezuela_1967 | 1.5 |
| venezuela_2026 | 1.6 |

### Marco teórico

- **Tectónica de placas:** geometría de límites (subducción, transformación, colisión) condiciona sismicidad regional.
- **Segmentación de fallas:** tasas de deslizamiento y sismicidad histórica informan periodos de retorno.
- **Catálogos vinculados:** analogía histórica para estimar escenarios futuros en el mismo corredor estructural.

---

## 7. Catálogo Fase 5 — modelos recomendados

### Salidas UI

| Elemento | Campos |
|---|---|
| Tabla catálogo | `dominio`, `modelo_recomendado`, `n_modelos_en_dominio` |
| Gráfica barras | conteo de modelos por dominio |

### Catálogo completo

**sismicidad (6 modelos)**

- ETAS
- Omori-Utsu
- Gutenberg-Richter
- Bayesian hierarchical models
- Hawkes processes
- Spatio-temporal clustering

**riesgo_territorial (10 modelos)**

- XGBoost
- LightGBM
- Random Forest
- Bayesian networks
- Graph Neural Networks
- Gaussian Processes espaciales
- Modelos geoespaciales con PySAL
- FCN geoespacial geologico
- ConvLSTM InSAR-temporal
- CNN geoespacial multicapa

**incertidumbre (5 modelos)**

- Monte Carlo
- Bayesian inference
- Quantile regression
- Conformal prediction
- Sensitivity analysis

### Marco teórico por dominio

| Dominio | Uso en el proyecto | Referencia conceptual |
|---|---|---|
| Sismicidad | Réplicas, clustering, magnitudes | Procesos puntuales auto-excitados (ETAS/Hawkes); leyes empíricas Omori y G-R |
| Riesgo territorial | Score compuesto, exposición, daño | ML tabular/geoespacial; redes bayesianas causales; GNN sobre grafos falla-ciudad-infra; **FCN geoespacial geológico** con capas InSAR/tectónica/suelo (§11) |
| Incertidumbre | Intervalos y sensibilidad | MC/Bayes para propagación; quantile regression y conformal prediction para bandas predictivas |

---

## 8. Proyección probabilística forward (Omori-Utsu + Gutenberg-Richter + regresión)

La UI y `scripts/project_venezuela_probabilities.py` comparten la lógica en `scripts/projection_model.py`.

**Importante:** la proyección es **forward desde la fecha de corte**, no acumulada desde el mainshock:

\[
N_{\text{add}} = N(t_{\text{fin}}) - N(t_{\text{elapsed}}), \quad t_{\text{fin}} = t_{\text{elapsed}} + \text{forward\_days}
\]

Donde \(t_{\text{elapsed}}\) = días transcurridos entre `main_event_date` y la fecha de corte.

### Salidas UI

| Elemento | Campos |
|---|---|
| Gráfica | `P(M ≥ M_objetivo)` (%) por `case_id` en la ventana forward |
| Tabla | ver columnas abajo |
| Gráfica de certeza histórica (absoluta) | `certainty_percent` (%) por `case_id` validado con eventos pasados |
| Gráfica ranking vs `venezuela_2026` | `certainty_vs_venezuela_2026_percent` (%) ordenado descendente; barra roja = referencia |
| Tabla de certeza histórica | `predicted_probability_m_ge_target`, `observed_event_reached`, `brier_score`, `certainty_percent`, `certainty_vs_venezuela_2026_percent` |

### Columnas de la tabla de proyección

| Columna UI | Significado |
|---|---|
| `scenario` | Escenario de calibración (`base`, `conservador`, `optimista`) |
| `as_of_date` | Fecha de corte seleccionada |
| `elapsed_days_from_main` | Días transcurridos desde mainshock hasta la fecha de corte |
| `forward_days` | Próximos N días proyectados desde la fecha de corte |
| `horizon_days_from_main` | `elapsed_days_from_main + forward_days` |
| `magnitude_target_mw` | Umbral M objetivo definido por usuario |
| `omori_K` | Constante Omori ajustada por escenario |
| `b_value` | b-value G-R ajustado por escenario |
| `additional_expected_aftershocks` | Réplicas esperadas en la ventana forward |
| `expected_max_magnitude_mw` | Estimación empírica de magnitud máxima esperada vía b-value |
| `expected_max_magnitude_capped_mw` | min(esperada, objetivo UI) |
| `probability_m_ge_target` | P(M ≥ objetivo) vía Poisson + G-R en ventana forward |
| `observed_max_magnitude_mw` | Máxima magnitud observada en catálogo hasta `as_of_date` |
| `linear_regression_slope_prob_per_day` | Pendiente de P(M≥objetivo) vs día en ventana forward |
| `linear_regression_r2` | Bondad de ajuste lineal (0–1) |

### Escenarios de calibración (K / b)

Definidos en `scripts/projection_model.py`. El escenario **conservador** aplica un factor extra sobre K cuando la magnitud máxima observada está por debajo del objetivo − 0.5 Mw (p. ej. Mmax 4.5 vs objetivo 6.0).

| Escenario | Factor K | Offset b | Ajuste extra si Mobs < Mobj − 0.5 |
|---|---:|---:|---|
| **Base** | 1.00 | +0.00 | — |
| **Conservador** | 0.82 | +0.12 | K × 0.88 |
| **Optimista** | 1.08 | −0.10 | — |

Límites de b ajustado: **[0.75, 1.20]**.

### Certeza histórica (%)

Para una ventana retrospectiva de `validation_days`, la UI compara predicción del modelo con lo que **sí** ocurrió en `highest_magnitude_events`.

Variable observada binaria:

\[
y =
\begin{cases}
1, & \text{si existe evento con } M \ge M_{\text{objetivo}} \text{ en } [0, validation\_days] \\
0, & \text{si no existe}
\end{cases}
\]

Con probabilidad modelada \(p = P(M \ge M_{\text{objetivo}})\), se calcula:

\[
\text{Brier} = (p - y)^2
\]
\[
\text{certainty\_percent} = (1 - \text{Brier}) \times 100
\]

Interpretación rápida:
- Certeza cercana a 100%: el modelo coincide bien con lo observado.
- Certeza baja: el modelo sobreestima o subestima el evento objetivo en esa ventana.

Índice comparativo explícito contra `venezuela_2026`:

\[
\Delta_{\text{vzla}} = \text{certainty\_percent}_{\text{caso}} - \text{certainty\_percent}_{\text{venezuela\_2026}}
\]
\[
\text{certainty\_vs\_venezuela\_2026\_percent} = 100 - |\Delta_{\text{vzla}}|
\]

- `certainty_delta_vs_venezuela_2026`: diferencia en puntos porcentuales vs referencia.
- `certainty_vs_venezuela_2026_percent`: cercanía de certeza al caso `venezuela_2026` (100 = igual).

### Parámetros fijos en UI

- Magnitud mínima de referencia: **Mw 4.0**
- Constante Omori **c = 1.0 día**
- Calibración base de **K** con `aftershock_count` y horizonte observado (`sequence_end_date` o máximo `days_after_main`)

### Ecuaciones implementadas

**Omori-Utsu (conteo acumulado):**

\[
N(t) = K \left[ (t+c)^{1-p} - c^{1-p} \right] / (1-p) \quad (p \neq 1)
\]

\[
N(t) = K \ln\frac{t+c}{c} \quad (p = 1)
\]

**Gutenberg-Richter (número esperado sobre umbral):**

\[
n_{\geq M} = N(t) \cdot 10^{-b(M - M_{\min})}
\]

**Probabilidad de al menos un evento ≥ M:**

\[
P(M \geq M_0) = 1 - e^{-n_{\geq M_0}}
\]

**Magnitud máxima esperada (aproximación):**

\[
M_{\max,\text{esp}} = M_{\min} + \frac{\log_{10} N(t)}{b}
\]

**Regresión lineal** sobre la serie diaria forward \( y_d = P(M \geq M_0 \mid d) \), con \(d\) desde `elapsed_days_from_main + 1` hasta `horizon_days_from_main`:

\[
y = \beta_0 + \beta_1 d, \quad R^2 = 1 - \frac{SS_{res}}{SS_{tot}}
\]

### Ejemplo operativo — `venezuela_2026` (corte 2026-06-29, forward 8 d, Mw 6.0)

Mainshock 2026-06-24 → **día 5** transcurrido. Mmax observada hasta corte: **Mw 4.5** (día 1).

| Escenario | K | b | N forward | P(M≥6.0) forward |
|---|---:|---:|---:|---:|
| Conservador | 27.32 | 1.02 | 23.15 | **19.0%** |
| Base | 37.86 | 0.90 | 32.08 | **39.9%** |
| Optimista | 40.89 | 0.80 | 34.64 | **58.1%** |

> **Nota de interpretación:** el valor acumulado legacy P(M≥6) = **73.24% a 8 días desde mainshock** (día 0→8) **no** equivale a la ventana operativa forward desde hoy. Para monitoreo en tiempo real usar siempre fecha de corte + días forward.

\* `venezuela_1812` tiene `aftershock_count = 0`; la proyección Omori queda degenerada (sin réplicas calibrables).

### PGA estimada — `venezuela_1967` (Sozen et al. 1968 NAS)

**Importante — sesgo de calibración:** no existían acelerógrafos fuertes operativos en Caracas durante el mainshock. Los valores provienen de **estimaciones post-evento** (daño estructural, sismoscopio Cajigal, estudios NAS). **No deben usarse para calibrar modelos forward de `venezuela_2026`** ni como ancla numérica en comparativas instrumentales: el sesgo metodológico y de sitio puede inflar o deflacionar PGA aparente frente a redes modernas.

Campo schema: `pga_measurement_quality: estimated_indirect` y `pga_calibration_bias_warning` en `advanced_features.seismic`.

| Ubicación | PGA (g) | Rango (g) | Método | Fuente |
|---|---:|---|---|---|
| Los Palos Grandes (Covent Garden) | 0.07 | 0.06–0.08 | Análisis pergola | Sozen et al. (1968) NAS |
| Valle metropolitano Caracas | 0.08 | — | Síntesis informe NAS | Sozen et al. (1968); NIST PB80119027 |
| Observatorio Cajigal (roca) | 0.071 | 0.012–0.071 | Sismoscopio | Fiedler (cit. Alonso 2017) |
| Superficie aluvial | 0.10 | 0.05–0.10 | Daño estructural | Skinner (1967) NAS companion |

Campo agregado en schema: `advanced_features.seismic.pga_station_estimates[]` con trazabilidad por estación/zona.

### Salidas UI (sección PGA)

| Elemento | Campos |
|---|---|
| Gráfica PGA agregada | `pga_g` (g) por `case_id`; barra roja resalta `venezuela_1967` |
| Gráfica PGA por estación | barras horizontales con barras de error `pga_g_min`–`pga_g_max` |
| Tabla resumen | `case_id`, `pga_g`, `mmi_intensity`, `station_estimates_count`, `pga_measurement_quality` |
| Tabla detalle | `location`, `pga_g`, rango, `site_class`, `estimate_method`, `source`, `notes` |
| Aviso sesgo | Markdown dinámico si hay `estimated_indirect` (p. ej. 1967 vs 2026) |
| Catálogos internacionales 2026 | Markdown con verificación USGS/GFZ/EMSC al seleccionar `venezuela_2026` |

Métrica **PGA (g)** también disponible en barras/dispersión del panel superior.

### Catálogos internacionales — evento 2026-06-24

Verificación FDSN al **2026-06-29** (`docs/venezuela_2026_international_catalog_verification.json`):

| Agencia | País | Resultado |
|---|---|---|
| **USGS** | EE. UU. | **9 eventos M≥4** — foreshock M7.2 (`us6000t7zc`, redes `at,us`), mainshock M7.5 (`us6000t7zp`), 7 réplicas M4.3–4.8 hasta 29-jun |
| GFZ Geofon | Alemania | Sin eventos en respuesta API (mismo bbox/ventana) |
| EMSC | UE | Sin eventos en respuesta API (mismo bbox/ventana) |

El repositorio local tenía réplicas documentadas solo hasta 26-jun; USGS añade actividad hasta 29-jun. GFZ aparece citado en fuentes tectónicas del caso pero no expone el catálogo en FDSN para esta consulta.

---

## 9. Inventario completo de features Fase 3 (schema)

Features registrados en `scripts/validation.py` (42 campos). No todos se muestran directamente en la UI, pero alimentan el modelo de riesgo y proyecciones.

### Sísmicas (`advanced_features.seismic`)

| Campo | En UI directa |
|---|---|
| magnitude_mw | Sí (barras/dispersión) |
| depth_km | Sí |
| focal_mechanism | No |
| distance_to_fault_km | No |
| estimated_slip_rate_mm_per_year | Sí |
| pga_g | Sí (comparativa y resumen) |
| pga_measurement_quality | Sí (tabla resumen PGA; aviso sesgo en UI) |
| pga_calibration_bias_warning | Sí (aviso sesgo PGA en UI) |
| pga_station_estimates | Sí (gráfica y tabla por zona/estación) |
| pgv_cm_per_s | No |
| mmi_intensity | No |
| aftershock_count | Sí |
| omori_decay_p | Sí |
| gutenberg_richter_b_value | Sí |
| local_seismic_density | No |

### Geológicas/geotécnicas (`advanced_features.geological_geotechnical`)

| Campo | En UI directa |
|---|---|
| soil_type | No |
| lithology | Sí (tabla geológica) |
| vs30_m_per_s | Sí |
| slope_degrees | No |
| sedimentary_basin | No |
| location_geology_context | Sí |
| nearby_geological_faults | Sí |
| nearby_tectonic_plates | Sí |
| faults_average_seismic_activity_events_per_year | Sí |
| fault_linked_relevant_events | Sí (resumen) |
| liquefaction_likelihood | No |
| landslide_susceptibility | No |
| distance_to_coast_or_rivers_km | No |

**Campos operativos InSAR/GNSS (fuera del schema de casos, vía workflow internacional + FCN):**

| Campo | En UI directa | Fuente |
|---|---|---|
| `insar_gnss_rows` (VSR/SSR/NSR) | No (ver §11) | `storage/venezuela/international/...` |
| `insar_displacement_cm` | No (ver §11) | Puente `geological_model/insar_bridge.py` |
| Salidas FCN (`geotechnical_vulnerability`, etc.) | No (ver §11) | `storage/geological_model/outputs/latest.json` |

### Climáticas (`advanced_features.climatic`)

| Campo | En UI directa |
|---|---|
| rainfall_7d_mm | No |
| rainfall_15d_mm | No |
| rainfall_30d_mm | Sí |
| soil_moisture_index | No |
| extreme_events | No |
| terrain_saturation | No |
| mass_movement_risk | No |

### Humanas/urbanas (`advanced_features.human_urban`)

| Campo | En UI directa |
|---|---|
| exposed_population | Sí |
| urban_density | No |
| building_type | No |
| average_building_height_m | No |
| construction_age_profile | No |
| hospitals_count | No |
| primary_roads_density_km_per_km2 | No |
| ports_airports_access | No |
| schools_count | No |
| critical_infrastructure | No |

---

## 10. Proyección Venezuela (script CLI, complemento)

Comando: `make project-venezuela`

| Salida | Contenido |
|---|---|
| `docs/venezuela_projection_<fecha>.json` | Proyección **forward** a horizontes 30/45 d (desde fecha de corte), parámetros Omori/G-R, blend bayesiano |
| `docs/venezuela_projection_<fecha>_events.csv` | Eventos con magnitud, fecha, localización (repo + USGS) |

Modelos: Omori-Utsu + Gutenberg-Richter + prior bayesiano de análogos (`venezuela_2026`, `venezuela_1812`).

---

## 11. Modelo FCN geoespacial geológico e integración InSAR/GNSS

Implementación fuera del dashboard comparativo principal, alineada con `docs/foco-geologico.md` y `docs/earthquake-venezuela-new-focus-Calculo.md` (§2.2 deformación del suelo).

### Comandos operativos

| Comando | Script | Salida principal |
|---|---|---|
| `make geological-model-run` | `scripts/run_geological_model.py` | `storage/geological_model/outputs/latest.json` |
| `make fetch-insar-gnss` | `scripts/fetch_insar_gnss.py` | `storage/geological_model/raw/insar_gnss_measured_windows.json` + JSON internacional actualizado |
| `make international-estimation` | `scripts/run_international_estimation.py` | `storage/venezuela/international/YYYY/MM/DD/international_estimation_*.json` |
| Estimación + GNSS medido | `... --use-live-insar-gnss` | Mismo JSON internacional con filas `measured` |

### Arquitectura FCN (`fcn_geoespacial_geologico`)

Proxy tabular multicapa (4 canales) sobre features Fase 3 ya implementadas en `event_cases/` y `case_library/`:

| Canal | Peso | Campos de entrada (schema) | Marco teórico |
|---|---:|---|---|
| InSAR | 0.20 | `insar_displacement_cm`, VSR/SSR/NSR vía puente internacional | Deformación superficial (SNAPHU/InSAR; proxy o GNSS MIDAS) |
| Tectónica | 0.30 | `distance_to_fault_km`, `estimated_slip_rate_mm_per_year`, `nearby_geological_faults` | Proximidad y acoplamiento con fallas activas (GEM/USGS) |
| Suelo | 0.30 | `vs30_m_per_s`, `slope_degrees` | Amplificación local NEHRP / site class |
| Hidro-geotecnia | 0.20 | `liquefaction_likelihood`, `landslide_susceptibility`, `soil_moisture_index`, `distance_to_coast_or_rivers_km` | Licuefacción y remoción en masa |

**Salidas del modelo** (`geological_model/fcn_model.py`):

| Salida | Rango | Uso |
|---|---|---|
| `geotechnical_vulnerability` | 0–1 | Complementa `component_scores.geotechnical_vulnerability` (Fase 4) |
| `liquefaction_probability` | 0–1 | Riesgo de licuefacción |
| `spatial_amplification_factor` | factor | Derivado de Vs30 (NEHRP-like) |
| `fault_coupling_index` | 0–1 | Acoplamiento tectónica + InSAR |
| `structural_damage_probability` | 0–1 | Daño estructural esperado |
| `landslide_probability` | 0–1 | Deslizamiento / remoción |
| `risk_category` | categoría | `riesgo_bajo` … `riesgo_critico` |

Configuración: `models/geological_geospatial_fcn.yaml`. Tests: `tests/test_geological_model.py`.

### Variables InSAR/GNSS (workflow internacional, Fase 2.2)

Tabla `insar_gnss_rows` en el payload internacional (`scripts/international_calculation_workflow.py`):

| Columna | Unidad | Descripción |
|---|---|---|
| `window_start` | fecha | Inicio de ventana temporal |
| `window_end` | fecha | Fin de ventana temporal |
| `vsr_mm_per_year` | mm/año | Tasa de deslizamiento **vertical** (InSAR/GNSS) |
| `ssr_mm_per_year` | mm/año | Tasa de deslizamiento **lateral** (plano horizontal) |
| `nsr_mm_per_year` | mm/año | Tasa **neta** \( \sqrt{VSR^2 + SSR^2} \) |
| `data_status` | enum | `measured`, `proxy_from_seismic_catalog`, `placeholder_pending_source` |
| `notes` | texto | Trazabilidad de fuente |

**Estados de calidad InSAR en el FCN:**

| `data_status` | `insar_quality` | Origen |
|---|---|---|
| `measured` | `instrumented_insar` | GNSS MIDAS NGL (56 estaciones en bbox Venezuela-Caribe) |
| `proxy_from_seismic_catalog` | `proxy_seismic_catalog` | Proxy desde `benioff_rate`, `delta_m`, `m_mean` de ventana internacional |
| (sin dato) | `unknown` | Canal InSAR neutral 0.5 |

### Puente internacional → FCN (`geological_model/insar_bridge.py`)

1. Lee `insar_gnss_rows` del último JSON en `storage/venezuela/international/`.
2. Empareja ventana con `time_window` del caso (`event_cases/` / `case_library/`).
3. Convierte VSR/SSR/NSR a `insar_displacement_cm`:

\[
d_{\text{cm}} = \frac{\sqrt{VSR^2 + SSR^2 + NSR^2} \cdot (d_{\text{ventana}}/365.25)}{10}
\]

4. Inyecta desplazamiento en el canal InSAR del FCN; cada predicción incluye bloque `insar_bridge` con ventana, tasas y fuente.

### Obtención de datos reales y reemplazo (`geological_model/insar_gnss_fetch.py`)

| Función | Rol |
|---|---|
| `fetch_measured_insar_gnss_rows()` | Descarga/agrega VSR/SSR/NSR por ventana |
| `replace_insar_gnss_rows()` | Sustituye filas proxy por medidas (misma ventana) |
| `fetch_and_replace_insar_gnss_rows()` | Obtiene + reemplaza en un paso |
| `fetch_and_replace_international_payload_file()` | Reemplaza y **persiste el JSON internacional** |
| `apply_insar_replacement_to_payload()` | Actualiza `insar_gnss_rows`, `insar_fetch_meta`, `geological_insar_bridge`, `insar_updated_at_utc` |

**Fuente GNSS:** [NGL MIDAS IGS14](https://geodesy.unr.edu/velocities/midas.IGS14.txt) — bbox 0.3°–13.5°N, −73.7° a −59.7°W.

**Persistencia:**

| Archivo | Contenido |
|---|---|
| `storage/geological_model/raw/ngl_midas_igs14.txt` | Cache catálogo MIDAS |
| `storage/geological_model/raw/insar_gnss_measured_windows.json` | Ventanas medidas |
| `storage/geological_model/outputs/latest.json` | Predicciones FCN por caso |
| `storage/venezuela/international/.../international_estimation_*.json` | Payload internacional (filas InSAR actualizables in-place) |

CLI de reemplazo (por defecto actualiza el JSON internacional del día `--as-of`):

```bash
python3 scripts/fetch_insar_gnss.py --international-json storage/venezuela/international/.../international_estimation_*.json
python3 scripts/fetch_insar_gnss.py --as-of 2026-07-01          # busca último JSON del día
python3 scripts/fetch_insar_gnss.py --no-update-international   # solo raw de ventanas
```

### Funciones de pérdida espacial (entrenamiento futuro)

Registradas en `geological_model/losses.py` según `docs/foco-geologico.md` §4:

| Función | Uso |
|---|---|
| `weighted_mse_mae` | Pérdida ponderada MSE-MAE para píxeles/eventos raros |
| `stpidn_combined_weights` | Pesos Gutenberg-Richter (magnitud) + distancia a fallas (epicentro) |
| `seismology_informed_mse_star` | MSE* penalizada vs modelo de referencia (p. ej. ETAS) |

### Relación con features UI existentes

El FCN consume las mismas variables geológicas/geotécnicas documentadas en §5, §6 y §9 (`vs30_m_per_s`, fallas cercanas, licuefacción, humedad de suelo). La UI comparativa **no expone aún** las salidas FCN; el JSON `storage/geological_model/outputs/latest.json` es la referencia operativa hasta integrar una pestaña dedicada.

---

## 12. Referencias y trazabilidad

- Implementación UI: `scripts/comparative_charts.py`
- Modelo compartido de proyección forward: `scripts/projection_model.py`
- Modelo FCN geológico: `geological_model/`, `scripts/run_geological_model.py`
- Puente y fetch InSAR/GNSS: `geological_model/insar_bridge.py`, `geological_model/insar_gnss_fetch.py`, `scripts/fetch_insar_gnss.py`
- Estimación internacional: `scripts/international_calculation_workflow.py`, `scripts/run_international_estimation.py`
- Contratos de datos: `schemas/comparable_event.schema.json`, `schemas/event_case.schema.json`
- Validación Fase 3/4/5: `scripts/validation.py`, `scripts/evaluate_phase5.py`
- Catálogo modelos: `models/recommended_models_phase5.yaml`
- Especificación FCN: `models/geological_geospatial_fcn.yaml`
- Proveedores InSAR/GNSS: `models/insar_gnss_providers.yaml`
- Marco geológico: `docs/foco-geologico.md`
- Datos comparativos: `case_library/*/event.yaml`
- Salidas geológicas: `storage/geological_model/outputs/`
- Salidas internacionales: `storage/venezuela/international/`

### Lecturas sugeridas

- Utsu, T. — Aftershock activity (Omori law, modified Omori).
- Gutenberg, B. & Richter, C. — Frequency-magnitude relation.
- Ogata, Y. — ETAS model for seismicity.
- NEHRP — Vs30 site classification for seismic design.
- Blewitt et al. — MIDAS GNSS velocities (NGL).
- `docs/foco-geologico.md` — capas InSAR, FCN, ConvLSTM y pérdidas espaciales.

---

*Generado para EarthquakeAnalysis. Actualizar este documento cuando cambien controles UI, métricas, schemas o pipelines geológicos/InSAR.*
