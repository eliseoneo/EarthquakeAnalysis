---
name: tdd-cycle
description: Ejecuta un ciclo corto red-green-refactor con pytest para cambios en schemas y datasets sismicos. Usar cuando se agregan campos o validaciones.
disable-model-invocation: true
---

# TDD Cycle

## Objetivo

Aplicar un ciclo rapido para cambios en `schemas/`, `event_cases/`, `case_library/` y `tests/`.

## Pasos

1. Red: crear/ajustar prueba que falle por el nuevo requisito.
2. Green: cambiar schema o fixture para pasar la prueba.
3. Refactor: simplificar y mantener consistencia de nombres.
4. Ejecutar `make test` y reportar resultado.

## Criterios

- No cerrar la tarea sin pruebas verdes.
- Evitar fixtures grandes; usar solo campos necesarios.

