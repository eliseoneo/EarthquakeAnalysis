# FUNVISIS - Análisis de Fuente de Datos y Estrategia de Integración

## Objetivo

Documentar la estructura observada de la fuente de datos de FUNVISIS, sus capacidades actuales, limitaciones y recomendaciones de integración para el proyecto EarthquakeAnalysis.

---

# Resumen Ejecutivo

FUNVISIS constituye la fuente oficial venezolana para eventos sísmicos.

Durante el análisis se identificó una fuente JSON pública utilizada por proyectos externos para consultar eventos sísmicos recientes.

La información disponible permite construir procesos ETL para monitoreo y almacenamiento histórico local.

Importante:

- No se identificó una API pública documentada con filtros avanzados.
- La fuente observada parece orientada a eventos recientes.
- Debe complementarse con fuentes internacionales para análisis históricos de largo plazo.

---

# Endpoint Identificado

```text
https://www.funvisis.gob.ve/maravilla.json
```

Método:

```http
GET /maravilla.json
```

Tipo de respuesta:

```text
application/json
```

---

# Estructura General Observada

La respuesta utiliza una estructura similar a GeoJSON.

Ejemplo simplificado:

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

---

# Campos de Interés

## Geometría

| Campo | Descripción |
|---------|---------|
| geometry.type | Tipo geométrico |
| geometry.coordinates[0] | Longitud |
| geometry.coordinates[1] | Latitud |

---

## Propiedades

| Campo | Descripción |
|---------|---------|
| value | Magnitud |
| depth | Profundidad |
| date | Fecha |
| time | Hora |
| country | País |
| addressFormatted | Ubicación descriptiva |
| lat | Latitud |
| long | Longitud |

---

# Modelo Normalizado Recomendado

```json
{
  "event_id": "",
  "source": "FUNVISIS",
  "event_time_utc": "",
  "latitude": 0.0,
  "longitude": 0.0,
  "magnitude": 0.0,
  "depth_km": 0.0,
  "location_description": "",
  "country": "Venezuela"
}
```

---

# Limitaciones Detectadas

## Sin filtros observados

No se identificaron parámetros públicos para:

- fecha inicio
- fecha fin
- magnitud mínima
- magnitud máxima
- profundidad
- región
- bounding box

Por tanto:

```text
La consulta descarga la colección completa disponible.
```

---

## Histórico limitado

La fuente observada parece enfocada en eventos recientes.

No se identificó:

- catálogo histórico por API
- consultas de décadas anteriores
- endpoints especializados para eventos históricos

---

# Estrategia ETL Recomendada

## Paso 1

Descarga del JSON fuente

```text
GET https://www.funvisis.gob.ve/maravilla.json
```

---

## Paso 2

Validación de estructura

Validar:

- existencia de FeatureCollection
- features no vacías
- propiedades mínimas

---

## Paso 3

Normalización

Convertir:

```text
depth -> float (km)
value -> float (magnitud)
date + time -> timestamp UTC
```

---

## Paso 4

Generación de Event ID

Ejemplo:

```text
SHA256(
fecha +
hora +
latitud +
longitud +
magnitud
)
```

---

## Paso 5

Persistencia

Guardar:

### RAW

```text
json/
  yyyy/
    mm/
      dd/
```

### Curated

```text
parquet/
csv/
postgres/
timescaledb/
```

---

## Paso 6

Detección de nuevos eventos

Comparar:

- event_id
- timestamp
- coordenadas

Insertar únicamente eventos nuevos.

---

# Arquitectura Recomendada

FUNVISIS
↓
Raw Zone
↓
Normalización
↓
Catálogo Sísmico Venezuela
↓
Data Lake Global
↓
Modelos Analíticos

---

# Uso Dentro del Proyecto EarthquakeAnalysis

## Capa A - Tectónica Principal

Variables:

- magnitud
- profundidad
- localización
- tiempo
- frecuencia de eventos

---

## Casos de Uso

### Monitoreo en tiempo real

Detección automática de nuevos eventos.

### Correlación internacional

Comparar contra:

- USGS
- ISC
- GCMT

### Estudios históricos

Complementar con:

- FUNVISIS
- USGS
- ISC
- IRIS

### Evaluación de hipótesis

Aplicable al análisis:

- Cariaco 1997
- Venezuela 2026
- secuencias sísmicas
- dobletes sísmicos
- migración de réplicas

---

# Recomendación Final

FUNVISIS debe considerarse:

- Fuente oficial venezolana.
- Fuente prioritaria para eventos nacionales.
- Complementaria a catálogos internacionales.
- Entrada principal para monitoreo operativo en Venezuela.

No debe utilizarse como única fuente para análisis históricos de largo plazo.
