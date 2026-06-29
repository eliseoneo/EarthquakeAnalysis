# AGENTS

## Objetivo operativo

Este repositorio prioriza tres fases:

1. `event_cases/venezuela_2026_june` (post-evento).
2. `case_library/*` (comparacion con eventos analogos).
3. Feature engineering avanzado (sismico, geotecnico, climatico y humano/urbano).

## Reglas de colaboracion entre agentes

- Trabajar en paralelo por carpeta objetivo cuando sea posible:
  - Agente A: `event_cases/`
  - Agente B: `case_library/`
  - Agente C: `schemas/` + `tests/`
- Mantener el mismo contrato de campos definido en `schemas/`.
- No mezclar datos reales con sinteticos en una misma ruta.
- Toda nueva variable debe registrarse primero en schema y despues en datos.

## Flujo minimo

1. Definir o actualizar schema.
2. Crear/actualizar datos del caso.
3. Crear/actualizar variables de Fase 3 en datos del caso.
4. Ejecutar evaluaciones por fase (`make eval-phase1`, `make eval-phase2`, `make eval-phase3`) o completa (`make evaluate`).
5. Reportar cambios y riesgos de consistencia.

