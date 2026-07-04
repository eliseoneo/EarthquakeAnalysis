# ISC - International Seismological Centre

## Rol

Catálogo global revisado de terremotos, orientado a investigación histórica y validación científica.

## Sitios oficiales

- https://www.isc.ac.uk/
- https://www.isc.ac.uk/iscbulletin/
- https://www.isc.ac.uk/fdsnws/event/1/

## Base FDSN observada

```text
https://www.isc.ac.uk/fdsnws/event/1/
```

## Uso principal

- Histórico de largo plazo.
- Comparación con catálogos regionales.
- Refinamiento de localización y magnitud.
- Validación post-evento.

## Formatos esperados

Al ser compatible con FDSN Event, puede soportar formatos típicos como:

- QuakeML
- text
- xml

Verificar formato soportado en la instancia activa antes de automatizar.

## Estrategia ETL

1. Consultar por ventana temporal.
2. Normalizar a `earthquake_event.schema.json`.
3. Enlazar con USGS por tiempo, lat/lon y magnitud.
4. Marcar como fuente revisada.
