# Proyecto de Analisis Sismico: Nuevo Layout Operativo Venezuela

Este documento redefine el flujo de desarrollo para mantener consistencia con la arquitectura del repositorio y localizar fuentes oficiales de datos sismologicos para Venezuela y region.

## 1. Objetivo Operativo

1. Alinear la documentacion con las fases operativas del proyecto.
2. Mantener aisladas las capas de datos tectonicos (Capa A) y geofisicos ambientales (Capa B).
3. Localizar fuentes oficiales: USGS, INGV (Italia), SGC (Colombia), con USGS como fallback regional.
4. Dejar codigo ejecutable para consulta, normalizacion y comparacion inicial de catalogos.

## 2. Estructura de Desarrollo (Fases 1-5 + Capas A/B)

### 2.1 Fases Operativas

1. Fase 1: Post-evento en event_cases.
2. Fase 2: Libreria comparativa en case_library.
3. Fase 3: Feature engineering avanzado (sismico, geotecnico, climatico, humano-urbano).
4. Fase 4: Modelo de riesgo compuesto.
5. Fase 5: Catalogo de modelos recomendados.

### 2.2 Capas Aisladas

1. Capa A (tectonica): layer_a_tectonic y paquete layer_a.
2. Capa B (geofisica ambiental): layer_b_geophysical y paquete layer_b.

Regla critica:
1. No mezclar datos de Capa A con Fases 1-5.
2. No mezclar datos de Capa B con Fases 1-5 ni con Capa A.
3. No mezclar raw y sintetico en la misma ruta.

## 3. Flujo de Datos Recomendado

1. Ingesta de catalogos sismicos oficiales en Capa A.
2. Normalizacion y deduplicacion en Capa A.
3. Persistencia de resultados tectonicos en rutas de Capa A.
4. Referencia derivada en event_cases y case_library mediante campos del esquema.
5. Validacion por fases y capas con comandos make.

## 4. Fuentes Oficiales Localizadas

### 4.1 USGS (Oficial)

1. API FDSN Event: https://earthquake.usgs.gov/fdsnws/event/1/
2. Endpoint de consulta tipico: https://earthquake.usgs.gov/fdsnws/event/1/query

### 4.2 INGV Italia (Oficial)

1. Portal oficial terremotos INGV: https://terremoti.ingv.it/
2. Referencia de servicios y software: https://terremoti.ingv.it/en/webservices_and_software

Nota:
1. Si un endpoint especifico cambia o esta temporalmente restringido, usar el portal oficial como fuente primaria validada y registrar el metodo de acceso usado en el reporte tecnico.

### 4.3 Colombia (Oficial)

1. Portal oficial de sismos SGC: https://www.sgc.gov.co/sismos
2. Detalles de evento (patron): https://www.sgc.gov.co/detallesismo/<EVENT_ID>/resumen

Fallback regional para Colombia:
1. USGS FDSN Event API (misma interfaz de 4.1), para comparacion y consolidacion transfronteriza.

## 5. Codigo Ejecutable: Consulta de Catalogos

### 5.1 USGS por ventana temporal y bbox Venezuela

```bash
curl -s "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=2026-06-24&endtime=2026-06-30&minlatitude=0&maxlatitude=16&minlongitude=-74&maxlongitude=-58&orderby=time-asc" \
  | jq '.features | length'
```

### 5.2 SGC: pagina oficial de sismos Colombia

```bash
curl -s "https://www.sgc.gov.co/sismos" | head -n 40
```

### 5.3 INGV: portal oficial de terremotos

```bash
curl -s "https://terremoti.ingv.it/" | head -n 40
```

### 5.4 Python: normalizacion minima para comparacion cruzada

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class QuakeEvent:
  source: str
  event_id: str
  origin_utc: datetime
  magnitude: float | None
  latitude: float | None
  longitude: float | None
  depth_km: float | None


def _to_utc(dt: datetime) -> datetime:
  if dt.tzinfo is None:
    return dt.replace(tzinfo=timezone.utc)
  return dt.astimezone(timezone.utc)


def parse_usgs_feature(feature: dict[str, Any]) -> QuakeEvent:
  props = feature.get("properties", {})
  geom = feature.get("geometry", {})
  coords = geom.get("coordinates", [None, None, None])

  origin_ms = props.get("time")
  origin = datetime.fromtimestamp(origin_ms / 1000, tz=timezone.utc) if origin_ms else datetime.now(timezone.utc)

  return QuakeEvent(
    source="USGS",
    event_id=str(feature.get("id", "")),
    origin_utc=_to_utc(origin),
    magnitude=props.get("mag"),
    latitude=coords[1],
    longitude=coords[0],
    depth_km=coords[2],
  )


def parse_generic_event(source: str, event_id: str, origin_iso: str, mag: float | None, lat: float | None, lon: float | None, depth_km: float | None) -> QuakeEvent:
  # Util para mapear eventos provenientes de SGC/INGV cuando se dispone de campos equivalentes.
  return QuakeEvent(
    source=source,
    event_id=event_id,
    origin_utc=_to_utc(datetime.fromisoformat(origin_iso.replace("Z", "+00:00"))),
    magnitude=mag,
    latitude=lat,
    longitude=lon,
    depth_km=depth_km,
  )
```

## 6. Integracion con la Estructura del Repositorio

1. Ingesta y descarga de catalogos:
   1. layer_a/ingestion
   2. layer_a/pipeline.py
2. Configuracion de prioridades de fuente:
   1. layer_a_tectonic/config/default.yaml
3. Persistencia tectonica:
   1. layer_a_tectonic/data
   2. layer_a_tectonic/persistence
4. Consumo en casos y comparables (sin copiar raw):
   1. event_cases/*/event.yaml
   2. case_library/*/event.yaml

## 7. Contrato de Datos y Consistencia

1. Registrar variables primero en schema y despues en datos.
2. Esquemas de referencia:
   1. schemas/event_case.schema.json
   2. schemas/comparable_event.schema.json
3. Validadores operativos:
   1. scripts/validation.py
   2. scripts/evaluate_phase1.py
   3. scripts/evaluate_phase3.py
   4. scripts/evaluate_phase4.py
   5. scripts/evaluate_phase5.py

## 8. Verificacion Ejecutable del Layout

```bash
make eval-phase1
make eval-phase3 --full
make eval-phase4 --full
make eval-phase5
make evaluate
```

Validacion de capas aisladas:

```bash
make layer-a-run
make layer-b-run
```

## 9. Alcance de Esta Iteracion

Incluye:
1. Nuevo layout documental operativo.
2. Localizacion de fuentes oficiales (USGS, INGV, SGC).
3. Codigo ejecutable para consulta y normalizacion inicial.

No incluye:
1. Implementacion productiva de conectores INGV/SGC en layer_a.
2. Cambios de schema fuera de los ya existentes.
