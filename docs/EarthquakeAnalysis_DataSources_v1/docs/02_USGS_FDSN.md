# USGS FDSN Event API

## Rol

Catálogo sísmico global de alta disponibilidad para eventos recientes e históricos.

## Documentación oficial

- https://earthquake.usgs.gov/fdsnws/event/1/

## Base URL

```text
https://earthquake.usgs.gov/fdsnws/event/1/
```

## Endpoint principal

```text
https://earthquake.usgs.gov/fdsnws/event/1/query
```

## Formatos

- geojson
- csv
- quakeml
- text

## Parámetros frecuentes

| Parámetro | Uso |
|---|---|
| format | geojson, csv, quakeml |
| starttime | fecha inicio |
| endtime | fecha fin |
| minmagnitude | magnitud mínima |
| maxmagnitude | magnitud máxima |
| latitude | centro latitud |
| longitude | centro longitud |
| maxradiuskm | radio km |
| minlatitude/maxlatitude | bbox |
| minlongitude/maxlongitude | bbox |
| mindepth/maxdepth | profundidad |
| orderby | time, magnitude |

## Ejemplo

```http
GET https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=2026-06-24&endtime=2026-06-26&minmagnitude=4&minlatitude=0&maxlatitude=15&minlongitude=-75&maxlongitude=-55
```

## Uso en EarthquakeAnalysis

- Catálogo global base.
- Comparación con FUNVISIS.
- Detección de secuencias y réplicas.
- Construcción de baseline histórico.
