# EarthquakeAnalysis Data Sources v1

Paquete de documentación técnica para integrar fuentes externas de datos sísmicos, acelerográficos, ambientales y satelitales.

## Contenido

```text
docs/      Documentación por fuente
schemas/   JSON Schemas normalizados
examples/  Ejemplos de consultas HTTP/Python
roadmap/   Capas analíticas del proyecto
```

## Uso sugerido

1. Importar este directorio en Cursor, VS Code o repositorio Git.
2. Usar `docs/00_Master_Data_Catalog.md` como índice.
3. Implementar conectores ETL por fuente.
4. Persistir raw/normalized/curated.
5. Validar cada fuente antes de automatización productiva.

## Nota

FUNVISIS incluye un endpoint observado, pero no documentado oficialmente como API pública estable.
