# EarthquakeAnalysis

Proyecto inicial para analisis sismico con dos fases activas:

1. Modulo post-evento `event_cases/venezuela_2026_june`.
2. Libreria comparativa global en `case_library`.

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

## Uso rapido

```bash
python3 -m pip install -e ".[dev]"
make test
```

