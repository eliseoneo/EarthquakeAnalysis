# ECMWF / Copernicus CDS - ERA5

## Rol

Reanálisis climático global para presión, humedad, precipitación, temperatura, viento y variables ambientales.

## Documentación oficial

- https://cds.climate.copernicus.eu/how-to-api
- https://cds.climate.copernicus.eu/user-guide

## Acceso

Requiere cuenta y token CDS API.

Archivo esperado:

```text
~/.cdsapirc
```

Ejemplo:

```yaml
url: https://cds.climate.copernicus.eu/api
key: <PERSONAL-ACCESS-TOKEN>
```

## Librería

```bash
pip install cdsapi
```

## Dataset común

```text
reanalysis-era5-single-levels
```

## Variables útiles

- mean_sea_level_pressure
- total_precipitation
- 2m_temperature
- 2m_dewpoint_temperature
- soil_temperature_level_1
- volumetric_soil_water_layer_1
- 10m_u_component_of_wind
- 10m_v_component_of_wind

## Uso en EarthquakeAnalysis

- Capa B: presión, lluvia, humedad y saturación de suelo.
- Comparación antes/después del evento.
- Features ambientales para modelos exploratorios.

## Nota

Las variables climáticas no predicen terremotos por sí solas. Deben usarse como contexto ambiental y no como causalidad directa sin validación estadística fuerte.
