# Global CMT - Global Centroid Moment Tensor

## Rol

Fuente global para mecanismos focales y tensor de momento sísmico.

## Sitios oficiales

- https://www.globalcmt.org/
- https://www.globalcmt.org/CMTsearch.html

## Cobertura

El catálogo principal corre desde enero de 1976 hasta meses recientes; incluye Quick CMTs para eventos más recientes.

## Magnitudes objetivo

- Soluciones sistemáticas para terremotos globales M > 5.
- Quick CMTs para eventos grandes recientes.

## Datos relevantes

- Tensor de momento.
- Strike, dip, rake.
- Tipo de mecanismo.
- Profundidad centroidal.
- Momento sísmico.
- Magnitud Mw.

## Integración

GCMT suele funcionar mediante formularios/descargas, no como API REST moderna universal. Se recomienda:

1. Descargar resultados por ventanas temporales.
2. Parsear formato NDK.
3. Vincular con eventos USGS/ISC por tiempo y ubicación.
4. Guardar mecanismo focal en tabla separada.

## Uso en hipótesis

- Validar si dos eventos tienen mecanismos focales distintos.
- Evaluar dirección de ruptura.
- Clasificar fallamiento: normal, inverso, strike-slip u oblicuo.
