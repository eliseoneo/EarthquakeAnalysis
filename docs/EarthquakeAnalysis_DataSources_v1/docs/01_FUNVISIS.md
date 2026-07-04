# FUNVISIS - Fuente de Datos Venezuela

## Rol

Fuente oficial venezolana para actividad sísmica nacional.

## Sitios oficiales

- https://www.funvisis.gob.ve/
- https://www.funvisis.gob.ve/monitor.html
- https://www.funvisis.gob.ve/old/sis_reciente.php
- https://www.funvisis.gob.ve/old/descargas.php

## Endpoint observado no documentado oficialmente

```text
https://www.funvisis.gob.ve/maravilla.json
```

Este endpoint debe tratarse como observado/no garantizado. No se debe asumir estabilidad contractual.

## Método

```http
GET /maravilla.json
```

## Estructura observada

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Sismo",
      "geometry": {
        "type": "Point",
        "coordinates": [-70.59, 10.06]
      },
      "properties": {
        "depth": "9.0 km",
        "value": "3.0",
        "addressFormatted": "59 km al oeste de Carora",
        "time": "09:06",
        "country": "Venezuela",
        "date": "26-09-2025",
        "lat": "10.06",
        "long": "-70.59"
      }
    }
  ]
}
```

## Campos ETL

| Campo | Normalización |
|---|---|
| properties.value | magnitude |
| properties.depth | depth_km |
| properties.date + properties.time | event_time_local |
| geometry.coordinates[0] | longitude |
| geometry.coordinates[1] | latitude |
| properties.addressFormatted | location_description |

## Limitaciones

- No se confirmó documentación pública oficial del endpoint JSON.
- No se observaron filtros por fecha, magnitud, bbox o profundidad.
- Se recomienda complementar con USGS, ISC y GCMT para histórico.

## Estrategia ETL

1. Descargar JSON.
2. Guardar raw.
3. Validar `FeatureCollection`.
4. Normalizar tipos.
5. Crear `event_id` determinístico.
6. Comparar contra snapshot anterior.
7. Insertar nuevos eventos.
