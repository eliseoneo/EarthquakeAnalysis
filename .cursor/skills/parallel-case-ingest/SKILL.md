---
name: parallel-case-ingest
description: Divide la carga de trabajo por casos sismicos en paralelo, manteniendo consistencia de variables comparables y trazabilidad de fuentes.
disable-model-invocation: true
---

# Parallel Case Ingest

## Cuando usar

Cuando se necesite poblar o actualizar multiples carpetas en `event_cases/` y `case_library/`.

## Estrategia

1. Separar trabajo por grupos de casos (sin solapamiento de archivos).
2. Alinear todos los agentes al contrato de `schemas/`.
3. Consolidar resultados en una revision final de consistencia.

## Checklist de salida

- Campos comparables completos.
- `sources` documentado.
- Notas de calidad de datos cuando haya incertidumbre.

