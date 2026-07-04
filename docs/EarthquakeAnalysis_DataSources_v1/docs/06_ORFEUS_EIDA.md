# ORFEUS / EIDA

## Rol

Infraestructura europea para acceso a datos sísmicos, estaciones y formas de onda.

## Documentación oficial

- https://www.orfeus-eu.org/data/eida/
- https://www.orfeus-eu.org/data/eida/webservices/
- https://orfeus.readthedocs.io/en/latest/eida_example.html

## Servicios

EIDA implementa servicios FDSN estándar.

## Endpoints habituales

Ejemplos de familias de servicios:

```text
/fdsnws/station/1/query
/fdsnws/dataselect/1/query
```

La URL exacta puede variar por nodo EIDA. Usar federador/routing cuando sea posible.

## Datos

- StationXML.
- MiniSEED.
- Metadatos de redes europeas.
- Waveforms.

## Uso en EarthquakeAnalysis

- Comparar acelerografía y ondas de eventos europeos.
- Obtener datos de Italia, Grecia, Turquía, España, Islandia y región Mediterránea.
- Construir dataset comparativo contra Venezuela.

## Recomendación ETL

1. Resolver nodo EIDA.
2. Consultar estación.
3. Descargar MiniSEED.
4. Guardar metadatos StationXML.
5. Procesar con ObsPy.
