# NASA Earthdata / CMR

## Rol

Descubrimiento y acceso a datasets satelitales: MODIS, Landsat, SMAP, GRACE/GRACE-FO y otros productos EOSDIS.

## Documentación oficial

- https://www.earthdata.nasa.gov/engage/open-data-services-software/earthdata-developer-portal
- https://www.earthdata.nasa.gov/engage/open-data-services-software/earthdata-developer-portal/cmr-api
- https://cmr.earthdata.nasa.gov/search/site/docs/search/api
- https://harmony.earthdata.nasa.gov/docs

## Base CMR Search

```text
https://cmr.earthdata.nasa.gov/search/
```

## Endpoints comunes

```text
/collections.json
/granules.json
```

## Parámetros frecuentes

| Parámetro | Uso |
|---|---|
| short_name | nombre corto dataset |
| temporal | rango temporal |
| bounding_box | bbox lon/lat |
| point | punto geográfico |
| polygon | polígono |
| page_size | tamaño de página |

## Ejemplo conceptual

```http
GET https://cmr.earthdata.nasa.gov/search/granules.json?short_name=MODIS_PRODUCT&temporal=2026-06-24T00:00:00Z,2026-06-26T23:59:59Z&bounding_box=-75,0,-55,15
```

## Datasets candidatos

- MODIS: temperatura, vegetación, anomalías térmicas.
- Landsat: imágenes ópticas de alta resolución.
- SMAP: humedad del suelo.
- GRACE/GRACE-FO: cambios gravitacionales/almacenamiento de agua.
- SRTM/NASADEM: elevación.

## Uso en EarthquakeAnalysis

- Capa E satelital.
- Comparación pre/post-evento.
- Variables de terreno, humedad y exposición.
