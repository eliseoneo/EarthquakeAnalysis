# Fase 2: Construcción de Capas Geoespaciales (InSAR y Tectónica)

## 2.1 Procesamiento InSAR: Desenrollado de Fase (Phase Unwrapping)
La fase interferométrica original es cíclica y está acotada matemáticamente entre $[-\pi, \pi]$ o $[-2\pi, 2\pi]$ [1]. Para convertir estos ciclos en desplazamientos reales del terreno:
* **Algoritmo de Optimización:** Dado que el desenrollado es un problema matemático complejo de redes no lineales, utilizaremos el algoritmo SNAPHU (Statistical-cost, Network-flow Algorithm for Phase Unwrapping) [2].
* **Implementación en Python:** Automatizaremos la ejecución mediante la librería `subprocess` de Python, tomando como entrada los archivos de fase exportados tras aplicar el filtrado de Goldstein [3-5]. 
* **Conversión y Geocodificación:** La matriz continua de fase resultante se convierte a desplazamientos en centímetros y se proyecta sobre coordenadas geográficas reales (WGS84) cruzándola con el Modelo Digital de Elevación SRTM [6, 7].

## 2.2 Estructuración de la Capa Tectónica (Bases GEM y USGS)
La base de datos *Global Active Faults* de la Fundación GEM y los catálogos del USGS proporcionan los trazados vectoriales con las características sismogénicas [8].
* **Filtrado del Sistema Venezolano:** Utilizando la librería `geopandas`, extraeremos exclusivamente los polígonos de los sistemas transcurrentes involucrados en la ruptura: Boconó, San Sebastián, El Guayabo y Morón [9].
* **Extracción de Variables (Features):** De cada segmento vectorial extraeremos los metadatos críticos para el modelo predictivo, incluyendo: geometría de la falla, cinemática y su tasa de deslizamiento (*slip rate*) [8].
* **Homologación Espacial:** Reproyectaremos estos vectores para que compartan exactamente el mismo Sistema de Referencia de Coordenadas (CRS) que la matriz satelital InSAR generada en el paso anterior.

## 2.3 Integración Espacial y Variables de Distancia (Spatial Join)
Para conectar la deformación superficial con la fuente sísmica, uniremos la matriz InSAR con la red de fallas:
* **Cálculo de Distancia a Fallas:** Mediante `geopandas`, calcularemos la distancia euclidiana mínima desde cada píxel de la cuadrícula de estudio (como la zona afectada en La Guaira) hasta la traza vectorial de la Falla de San Sebastián.
* **Herencia de Atributos:** A través de un *Spatial Join*, cada sector de la cuadrícula adquirirá automáticamente las propiedades físicas de su falla más cercana (tasa de deslizamiento, profundidad y esfuerzos de Coulomb transferidos).

## 2.4 Estructuración de la Capa Geológica de Suelos ($V_{s30}$)
Esta capa es crítica para que el modelo aprenda a predecir la destrucción por amplificación sísmica:
* **Asignación del $V_{s30}$:** Utilizando cartografía geológica, mapearemos la velocidad de la onda de corte en los primeros 30 metros del subsuelo. Asignaremos valores bajos a los depósitos aluviales y sedimentos sueltos de La Guaira, y valores altos a las zonas de roca metamórfica firme [1].
* **Cálculo del Índice de Licuación:** Los suelos granulares saturados con bajo $V_{s30}$ (como los de la costa) pierden su resistencia al esfuerzo cortante por el aumento de la presión de poros durante el sismo, comportándose como un fluido [2]. El modelo utilizará el $V_{s30}$ como variable principal para predecir este nivel de licuación y colapso estructural.

## Fase 3: Arquitectura de Inteligencia Artificial para Mapas Multicapa

Dado que los datos de entrada son cuadrículas espaciales (matrices raster), los modelos tradicionales de Machine Learning no pueden capturar la dependencia geográfica. Las arquitecturas profundas óptimas para este enfoque son:

*   **Redes Neuronales Convolucionales (CNN):** Están diseñadas específicamente para datos con topología de cuadrícula [1]. A través de sus capas convolucionales y de agrupación (pooling), los núcleos (kernels) se deslizan sobre los mapas para extraer características espaciales locales, aprendiendo automáticamente la relación entre la deformación del suelo y las estructuras geológicas vecinas [1].
*   **Fully Convolutional Networks (FCN):** Son una evolución de las CNN que toman las capas de entrada y devuelven un nuevo mapa espacial continuo con probabilidades predictivas. Investigaciones en sismología han demostrado que las FCN logran pronosticar la distribución espacial de sismos con un rendimiento similar al de los complejos modelos sismológicos tradicionales (como ETAS), pero con una velocidad de cálculo varios miles de veces superior [2, 3].
*   **ConvLSTM (Híbrido CNN-LSTM):** Es la arquitectura definitiva para procesar la evolución temporal de los mapas. Mientras la componente CNN extrae las características espaciales estáticas de La Guaira (como las fallas y el tipo de suelo), las celdas LSTM capturan las dependencias temporales a largo plazo de las series de tiempo (como la deformación progresiva captada por el InSAR mes a mes) [4, 5].


## Fase 4: Funciones de Pérdida para Desbalance Espacial

Al procesar cuadrículas de mapas, el modelo se enfrenta a un desbalance extremo: la inmensa mayoría de los píxeles no registran sismos. Si se usan funciones de pérdida estándar, el modelo simplemente aprenderá a predecir "cero sismos" en todo el mapa. Para evitar que las muestras negativas dominen el gradiente de la red, se aplican funciones de pérdida espacialmente ponderadas:

* **Weighted MSE-MAE (Pérdida Ponderada MSE-MAE):** Esta función combina el error cuadrático medio (MSE) y el error absoluto medio (MAE). Asigna pesos matemáticos significativamente mayores ($w_i$) exclusivamente a los píxeles donde realmente ocurrieron sismos y a sus regiones circundantes [1, 2].
* **Pérdida Separada de Magnitud y Epicentro (STPiDN):** Divide el problema en dos funciones de pérdida distintas [3]. Para la magnitud, aplica pesos basados en la ley de Gutenberg-Richter, dando mayor importancia a los sismos grandes y raros [4, 5]. Para el epicentro, pondera el error basándose en la distancia a las fallas tectónicas más cercanas, forzando a la red a prestar atención a la geometría de las fallas [6, 7].
* **Pérdida informada por Sismología (MSE* y CE*):** Incorpora conocimiento experto modificando dinámicamente los pesos [8, 9]. Compara las predicciones de la red con un modelo sismológico estadístico de referencia (como el modelo ETAS) y penaliza fuertemente a la red en las zonas donde el modelo sismológico falla, forzándola a aprender patrones nuevos y difíciles [10].