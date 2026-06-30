# AGENTS

## Objetivo operativo

Este repositorio prioriza cinco fases y una capa tectónica aislada:

1. `event_cases/venezuela_2026_june` (post-evento).
2. `case_library/*` (comparacion con eventos analogos).
3. Feature engineering avanzado (sismico, geotecnico, climatico y humano/urbano).
4. Modelo de riesgo compuesto (ensemble jerarquico y salidas probabilisticas).
5. Catalogo de modelos recomendados por dominio (`models/recommended_models_phase5.yaml`).
6. **Capa A — Tectonica Principal** (`layer_a_tectonic/` + paquete `layer_a/`): pipeline de catálogos sísmicos, deduplicación, fallas/placas, réplicas y dobletes. **No mezclar datos** con `event_cases/` ni `case_library/`.
7. **Capa B — Geofísica Ambiental** (`layer_b_geophysical/` + paquete `layer_b/`): SST, presión, lluvia, humedad de suelo, mareas, índices climáticos, estadística correlacional y comparación internacional. **No mezclar datos** con fases 1-5 ni Capa A.

## Reglas de colaboracion entre agentes

- Trabajar en paralelo por carpeta objetivo cuando sea posible:
  - Agente A: `event_cases/`
  - Agente B: `case_library/`
  - Agente C: `schemas/` + `tests/`
  - Agente D: `layer_a_tectonic/` + `layer_a/` (Capa A, datos aislados)
  - Agente E: `layer_b_geophysical/` + `layer_b/` (Capa B, datos aislados)
- Mantener el mismo contrato de campos definido en `schemas/`.
- No mezclar datos reales con sinteticos en una misma ruta.
- No mezclar datos de Capa A (`layer_a_tectonic/`) con fases 1-5 (`event_cases/`, `case_library/`).
- No mezclar datos de Capa B (`layer_b_geophysical/`) con fases 1-5, Capa A ni entre raw/sintético en la misma ruta.
- Toda nueva variable debe registrarse primero en schema y despues en datos.

## Flujo minimo

1. Definir o actualizar schema.
2. Crear/actualizar datos del caso.
3. Crear/actualizar variables de Fase 3 en datos del caso.
4. Crear/actualizar modelo de riesgo compuesto de Fase 4 en datos del caso.
5. Ejecutar evaluaciones por fase (`make eval-phase1`, `make eval-phase2`, `make eval-phase3`, `make eval-phase4`, `make eval-phase5`) o completa (`make evaluate`).
6. Capa A: ejecutar pipeline (`make layer-a-run`) o UI (`make layer-a-ui`).
7. Capa B: ejecutar pipeline (`make layer-b-run`) o UI (`make layer-b-ui`).
8. Reportar cambios y riesgos de consistencia.

