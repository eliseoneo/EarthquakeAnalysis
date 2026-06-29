# EarthquakeAnalysis

Proyecto inicial para analisis sismico con tres fases activas:

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

Tambien incluye harness minimo para agentes en paralelo (rules + skills) y un area de pruebas con valores sinteticos.

## Estructura principal

- `AGENTS.md`: lineamientos operativos para agentes.
- `.cursor/rules/`: reglas persistentes del proyecto.
- `.cursor/skills/`: skills del proyecto para ciclo de trabajo.
- `event_cases/`: casos post-evento.
- `case_library/`: eventos analogos historicos/globales.
- `schemas/`: contratos JSON Schema.
- `tests/fixtures/synthetic/`: datos sinteticos de prueba.
- `tests/unit/`: validaciones de esquema y consistencia.
- `scripts/`: evaluaciones por fase (`evaluate_phase1.py`, `evaluate_phase2.py`, `evaluate_phase3.py`, `evaluate_all.py`).

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

# Las 3 fases en secuencia (fixtures sinteticos)
make eval-all

# Auditoria completa con datos reales (event_cases + case_library)
make eval-full

# Evaluacion completa (pytest + fases 1, 2 y 3 en fixtures)
make evaluate
```

Scripts directos:

```bash
python3 scripts/evaluate_phase1.py
python3 scripts/evaluate_phase2.py
python3 scripts/evaluate_phase3.py
python3 scripts/evaluate_all.py
```

Opciones utiles:

```bash
# Incluir datos reales en cada fase
python3 scripts/evaluate_phase1.py --full
python3 scripts/evaluate_phase2.py --full
python3 scripts/evaluate_phase3.py --full

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

La interfaz incluye tres vistas:
- barras comparativas por metrica
- dispersion entre dos metricas
- probabilidad de magnitud similar en dias posteriores, usando `similar_magnitude_probability_dates.highest_magnitude_events`
- tabla-resumen con `case_id`, `n_eventos_horizonte`, `n_similares` y `%`

Lanzar con Uvicorn (FastAPI + Gradio montado):

```bash
make ui-uvicorn
# o
python3 scripts/comparative_charts.py --use-uvicorn --host 0.0.0.0 --port 7860
```

