# Fuentes Globales de Datos Sísmicos, Acelerográficos y Geofísicos

## Objetivo

Construir un Data Lake Sísmico Global para análisis científico de terremotos, acelerografía, geodesia, oceanografía y meteorología, con énfasis en Venezuela y comparación contra eventos mundiales.

---

# 1. Catálogos Sísmicos Globales

## USGS Earthquake Program
Sitio: https://earthquake.usgs.gov

API:
https://earthquake.usgs.gov/fdsnws/event/1/

Datos:
- Magnitud
- Profundidad
- Epicentro
- Tiempo UTC
- ShakeMap
- Réplicas
- Mecanismos focales

Uso:
- Base global de eventos
- Entrenamiento de modelos
- Comparaciones históricas

---

## International Seismological Centre (ISC)

Sitio:
https://www.isc.ac.uk

Datos:
- Catálogos históricos
- Revisiones científicas
- Localizaciones refinadas

Uso:
- Estudios de largo plazo
- Series temporales >25 años

---

## European-Mediterranean Seismological Centre (EMSC)

Sitio:
https://www.emsc-csem.org

Datos:
- Eventos sísmicos europeos
- Intensidades observadas
- Reportes ciudadanos

---

## Global Centroid Moment Tensor (GCMT)

Sitio:
https://www.globalcmt.org

Datos:
- Tensor de momento sísmico
- Tipo de falla
- Orientación de ruptura
- Energía liberada

---

# 2. Redes Sismográficas Mundiales

## IRIS

Sitio:
https://service.iris.edu/fdsnws/

Datos:
- Formas de onda
- MiniSEED
- SAC
- Redes sísmicas globales

Uso:
- Análisis de ondas P
- Análisis de ondas S
- FFT
- Energía espectral

---

## ORFEUS

Sitio:
https://orfeus-eu.org

Datos:
- Redes sísmicas europeas
- GNSS
- Formas de onda

---

# 3. Acelerografía

## European Integrated Data Archive (EIDA)

Sitio:
https://www.orfeus-eu.org/data/eida/

Datos:
- Acelerómetros
- Sismómetros
- Formas de onda

---

## Engineering Strong Motion Database (ESM)

Sitio:
https://esm-db.eu

Datos:
- PGA
- PGV
- PSA
- Espectros de respuesta
- Registros acelerográficos

Uso:
Comparación con:
- Turquía 2023
- Italia
- Grecia
- Japón
- Chile

---

## Center for Engineering Strong Motion Data (CESMD)

Sitio:
https://www.strongmotioncenter.org

Datos:
- Acelerogramas
- Espectros de respuesta
- PGA
- PGV

---

# 4. GNSS y Geodesia

## Nevada Geodetic Laboratory

Sitio:
http://geodesy.unr.edu

Datos:
- Desplazamiento milimétrico
- Movimiento de placas

---

## UNAVCO / EarthScope

Sitio:
https://www.unavco.org

Datos:
- GNSS
- Geodesia
- Deformación cortical

---

# 5. Venezuela

## FUNVISIS

Sitio:
https://www.funvisis.gob.ve

Datos:
- Catálogo sísmico nacional
- Fallas activas
- Intensidades
- Información histórica

Eventos relevantes:
- Cariaco 1997
- Sistema de falla El Pilar
- Sistema de falla Boconó
- Sistema de falla San Sebastián

---

# 6. Oceanografía

## NOAA

Sitio:
https://www.noaa.gov

API:
https://api.tidesandcurrents.noaa.gov

Datos:
- Mareas
- Tsunamis
- SST
- Presión atmosférica

---

## Copernicus Marine Service

Sitio:
https://marine.copernicus.eu

Datos:
- Temperatura superficial del mar
- Corrientes
- Oleaje
- Variables oceánicas

---

# 7. Meteorología

## ECMWF

Sitio:
https://www.ecmwf.int

Datos:
- ERA5
- Temperatura
- Presión
- Humedad
- Reanálisis climático

---

## NASA EarthData

Sitio:
https://earthdata.nasa.gov

Datos:
- MODIS
- Landsat
- GRACE
- SMAP

Uso:
- Variables satelitales
- Humedad del suelo
- Cambios gravitacionales
- Observación terrestre

---

# Priorización para el Proyecto Venezuela 2026

Nivel 1:
1. FUNVISIS
2. USGS
3. ISC
4. GCMT

Nivel 2:
5. IRIS
6. ORFEUS
7. EIDA
8. ESM
9. CESMD

Nivel 3:
10. NOAA
11. Copernicus
12. ECMWF
13. NASA EarthData

---

# Arquitectura Recomendada del Data Lake

## Capa A - Tectónica Principal
- Eventos sísmicos
- Fallas
- Placas
- Profundidad
- Magnitud
- Réplicas
- Mecanismos focales

## Capa B - Geofísica Ambiental
- Mareas
- SST
- Presión atmosférica
- Humedad
- Precipitación
- Saturación de suelo

## Capa C - Acelerografía
- PGA
- PGV
- PSA
- Espectros de respuesta
- Registros acelerográficos

## Capa D - Geodesia
- GNSS
- Desplazamientos
- Deformación cortical
- Movimiento de placas

## Capa E - Satelital
- Landsat
- MODIS
- GRACE
- SMAP

## Capa F - Modelos Comparativos
- Cariaco 1997
- Chile 2010
- Japón 2011
- Turquía-Siria 2023
- Venezuela 2026

