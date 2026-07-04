# NOAA CO-OPS API

## Rol

Datos costeros y oceánicos para correlación ambiental: mareas, niveles de agua, predicciones, corrientes y meteorología costera.

## Documentación oficial

- https://api.tidesandcurrents.noaa.gov/api/prod/
- https://tidesandcurrents.noaa.gov/web_services_info.html
- https://api.tidesandcurrents.noaa.gov/mdapi/prod/

## Base URL Data API

```text
https://api.tidesandcurrents.noaa.gov/api/prod/datagetter
```

## Parámetros frecuentes

| Parámetro | Uso |
|---|---|
| product | water_level, predictions, air_temperature, wind, air_pressure |
| station | ID estación |
| begin_date | YYYYMMDD |
| end_date | YYYYMMDD |
| date | today, latest, recent |
| datum | MLLW, NAVD, etc. |
| units | metric/english |
| time_zone | gmt/local/ lst_ldt |
| format | json, csv, xml |
| application | nombre de app |

## Ejemplo

```http
GET https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=water_level&station=8724580&begin_date=20260624&end_date=20260626&datum=MLLW&units=metric&time_zone=gmt&format=json&application=EarthquakeAnalysis
```

## Uso en EarthquakeAnalysis

- Mareas antes/durante/después de eventos.
- Presión atmosférica costera.
- Correlación con tsunami/alertas.
- Variables ambientales para Capa B.
