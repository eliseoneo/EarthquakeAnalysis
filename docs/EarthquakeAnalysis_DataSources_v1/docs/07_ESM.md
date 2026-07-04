# ESM - Engineering Strong Motion Database

## Rol

Base europea-mediterránea de datos acelerográficos y strong motion.

## Documentación oficial

- https://esm-db.eu/
- https://esm-db.eu/esmws/eventdata/1/
- https://www.orfeus-eu.org/data/strong/

## Servicio machine-friendly

```text
https://esm-db.eu/esmws/eventdata/1/
```

## Datos disponibles

- Waveforms acelerográficos.
- Espectros de respuesta.
- PGA.
- PGV.
- PSA.
- Metadatos de eventos y estaciones.

## Cobertura

Eventos con magnitudes relevantes en Europa, Mediterráneo y Medio Oriente. ORFEUS indica uso para eventos M > 4.0 registrados en esas regiones.

## Filtros

El servicio eventdata indica filtrado por:

- network
- station
- event-id

Consultar `application.wadl` y `query-options` del servicio para automatización completa.

## Uso en EarthquakeAnalysis

- Comparar aceleración del suelo.
- Validar modelos de daño.
- Analizar PGA/PGV vs distancia.
- Comparar eventos europeos con Venezuela 2026.
