# Catálogo Maestro de Fuentes de Datos - EarthquakeAnalysis

## Objetivo

Este paquete documenta fuentes externas reales para construir un Data Lake sísmico, acelerográfico, geodésico, oceánico, meteorológico y satelital.

## Fuentes incluidas

| ID | Fuente | Dominio | Uso principal |
|---|---|---|---|
| 01 | FUNVISIS | Venezuela | Sismos nacionales recientes |
| 02 | USGS FDSN Event | Global | Catálogo sísmico global |
| 03 | ISC | Global | Catálogo revisado histórico |
| 04 | EarthScope/IRIS FDSN | Global | Ondas, estaciones y eventos |
| 05 | GCMT | Global | Tensor de momento sísmico |
| 06 | ORFEUS/EIDA | Europa | Ondas y metadatos de estaciones |
| 07 | ESM | Europa-Mediterráneo | Acelerografía y strong motion |
| 08 | CESMD | USA/global parcial | Strong motion y acelerogramas |
| 09 | NOAA CO-OPS | Costas USA | Mareas, agua, meteorología costera |
| 10 | ECMWF/CDS ERA5 | Global | Reanálisis climático |
| 11 | NASA Earthdata/CMR | Global | Satélite, MODIS, Landsat, SMAP, GRACE |

## Capas del proyecto

- Capa A: tectónica principal.
- Capa B: geofísica ambiental.
- Capa C: acelerografía.
- Capa D: GNSS/geodesia.
- Capa E: satélite.
- Capa F: modelos comparativos y riesgo.

## Regla de integración

Toda fuente debe almacenarse en tres niveles:

1. `raw`: respuesta original.
2. `normalized`: esquema común.
3. `curated`: dataset analítico enriquecido.

## Nota crítica

No todas las fuentes ofrecen APIs públicas completas. Algunas requieren registro, token, formularios web o descarga manual.
