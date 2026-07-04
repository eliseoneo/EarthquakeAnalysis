# EarthScope / IRIS FDSN Services

## Rol

Acceso a metadatos de estaciones y formas de onda sísmicas.

## Documentación oficial

- https://service.iris.edu/
- https://service.iris.edu/fdsnws/station/1/
- https://service.iris.edu/fdsnws/dataselect/1/

## Nota 2026

El servicio `fdsnws-event` de EarthScope/IRIS fue retirado en 2026. Para eventos, usar USGS, ISC o EMSC. Para estaciones y waveforms, usar servicios FDSN vigentes.

## Endpoints principales

```text
https://service.iris.edu/fdsnws/station/1/query
https://service.iris.edu/fdsnws/dataselect/1/query
```

## Formatos

- StationXML
- text
- MiniSEED

## Parámetros station

| Parámetro | Uso |
|---|---|
| network | red |
| station | estación |
| channel | canal |
| starttime/endtime | ventana |
| latitude/longitude/maxradius | búsqueda radial |
| level | network, station, channel, response |

## Parámetros dataselect

| Parámetro | Uso |
|---|---|
| net | red |
| sta | estación |
| loc | location code |
| cha | canal |
| starttime | inicio |
| endtime | fin |

## Uso en EarthquakeAnalysis

- Descargar ondas P/S.
- Calcular FFT, energía espectral y duración.
- Comparar respuesta por distancia epicentral.
