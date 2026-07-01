# Proyecto de Predicción Sísmica: Extracción y Procesamiento de Datos

## Fase 1: Definición de Ventanas Espacio-Temporales
* **Zonificación Tectónica:** Agrupación por bloques tectónicos activos y sistemas de fallas para mejorar la captura de características físicas.
* **Cuadrículas Espaciales:** División en celdas (ej. 2° x 2° o 0.1° x 0.1°) con solapamiento.
* **Ventana Temporal Deslizante (Sliding Window):** Observaciones agrupadas en periodos retrospectivos (ej. los últimos 2 años) que se deslizan progresivamente (ej. mes a mes) para crear múltiples muestras.

## Fase 2: Ingeniería de Características (Feature Engineering)

### 2.1 Variables Predictivas del Catálogo Sísmico
Dentro de cada ventana espacio-temporal, se calcularán los siguientes indicadores [1]:
* **Frecuencia sísmica ($N$):** Cantidad total de eventos registrados [1].
* **Magnitud media ($M_{mean}$):** Promedio de las magnitudes en la ventana [1].
* **Parámetros de Gutenberg-Richter:** El valor $b$ (que marca la proporción estadística entre sismos grandes y pequeños) y el valor $a$ (tasa de sismicidad base) [1, 2].
* **Deformación de Benioff ($dE^{1/2}$):** Tasa de liberación de la raíz cuadrada de la energía sísmica, útil para medir el estrés elástico acumulado [1, 3].
* **Diferencia de magnitud ($\Delta M$):** Magnitud máxima observada menos la máxima esperada matemáticamente [1, 4].
* **Intervalo de recurrencia ($\mu$):** Tiempo medio transcurrido entre los sismos registrados [1, 5].
* **Desviación cuadrática media ($\eta$):** Error del ajuste estadístico en la línea de regresión [1, 6].

### 2.2 Variables de Deformación del Suelo (InSAR/GNSS)
* **Tasa de deslizamiento vertical (VSR):** Estimada a partir de radares satelitales y mediciones de subsidencia/elevación [7].
* **Tasa de deslizamiento lateral (SSR):** Vectores de desplazamiento en el plano horizontal [7].
* **Tasa de deslizamiento neto (NSR):** Cálculo geométrico que integra VSR, SSR y el buzamiento de la falla [7].

## Fase 3: Definición de la Variable Objetivo (Target)
El problema puede abordarse desde dos enfoques predictivos principales [1]:
* **Clasificación Binaria:** Predecir la probabilidad de ocurrencia (1) o no ocurrencia (0) de un sismo que supere una magnitud umbral (por ejemplo, $M \ge 5.0$) dentro de una ventana espacio-temporal específica [2, 3].
* **Regresión:** Predecir el valor numérico exacto de la magnitud máxima esperada ($M_{max}$) en la siguiente ventana de tiempo (ej. el próximo año) [3, 4]. 

## Fase 4: Selección de Algoritmos de Machine Learning
Dada la naturaleza compleja y no lineal de los datos sísmicos y de deformación, los algoritmos que han demostrado mejor rendimiento incluyen:
* **Modelos basados en Árboles (Random Forest y GBDT):** Son altamente efectivos para manejar las características físicas y estadísticas extraídas de las ventanas espaciales [5, 6]. 
* **Ensambles (Stacking):** La técnica de *Stacking*, que combina predicciones de modelos base como Random Forest y GBDT, ha demostrado ofrecer la mayor precisión y robustez para pronosticar magnitudes máximas anuales basándose en zonificación sísmica [7, 8].
* **Redes LSTM (Long Short-Term Memory):** Son ideales para procesar las series temporales puras, ya que sus mecanismos de memoria capturan de forma excelente las dependencias a largo plazo en la actividad sísmica de una zona específica [4, 7].

## Fase 5: Funciones de Pérdida (Loss Functions) para Datos Desbalanceados
En sismología, los días sin eventos dominan abrumadoramente sobre los días con sismos destructivos. Si usas funciones estándar, el modelo aprenderá a predecir siempre "no sismo". Para evitarlo, se recomiendan:
* **Balanced Cross Entropy (BCE):** Ajusta los pesos de la función para priorizar fuertemente las predicciones de la clase minoritaria (sismos grandes) [1].
* **Focal Loss (FL):** Asigna penalizaciones más altas a los ejemplos "difíciles" y reduce drásticamente el peso de los ejemplos fáciles, enfocando el aprendizaje en los casos complejos [2, 3].
* **GHMC (Gradient Harmonization Mechanism Classification):** Ajusta dinámicamente los pesos basándose en la densidad de los gradientes para armonizar la influencia de muestras fáciles y difíciles [4-6].
* **Pérdida Ponderada MSE-MAE:** Asigna mayores pesos específicamente a las regiones espaciales donde ocurren sismos para evitar que las muestras negativas dominen el gradiente de la red [7, 8].

## Fase 6: Métricas de Evaluación
Usar métricas de clasificación estándar como la "Exactitud" (Accuracy) es un error grave en sismología; un modelo que prediga que "nunca habrá sismos" tendría un 99% de exactitud, pero cero utilidad [9, 10].
* **Para Regresión (predecir magnitudes numéricas):** Error Cuadrático Medio (MSE) para medir la magnitud del error, y el Coeficiente de Determinación ($R^2$) para evaluar el ajuste [11, 12].
* **Para Clasificación (ocurrencia o no de sismos mayores a una magnitud):** F1-score, Geometric Mean (GM) y el Área Bajo la Curva de Precisión-Exhaustividad (PRC) [13-15].
* **Métricas Especializadas de Sismología (Las más rigurosas):** 
  * **Diagrama de Molchan:** La métrica por excelencia para alarmas sísmicas. Compara la tasa de eventos omitidos frente a la fracción de volumen espacio-temporal bajo alerta [16-18]. 
  * **L-test y S-test:** Evalúan la verosimilitud de la distribución temporal y espacial de tu modelo frente a la actividad sísmica real [19-21].

## Fase 7: Validación y División de Datos
En la predicción sísmica, mezclar datos del futuro con el pasado en el conjunto de entrenamiento arruina la validez del modelo. Para evaluarlo, la sismología emplea tres protocolos estrictos:
* **Pruebas Prospectivas:** Las predicciones se formulan en tiempo real y se evalúan estrictamente contra los sismos que ocurren después del pronóstico [1, 2]. Es el "estándar de oro" porque elimina cualquier sesgo, pero requiere esperar a que ocurran los eventos [1, 2].
* **Pruebas Retrospectivas:** Se compara el modelo con catálogos de terremotos del pasado [1, 2]. Aunque es útil para fases iniciales, es muy susceptible a que el desarrollador ajuste el modelo para que encaje perfectamente con los datos ya conocidos (sobreajuste) [1, 2].
* **Pruebas Pseudo-prospectivas (Recomendado):** Un método híbrido donde el modelo se entrena utilizando únicamente datos registrados hasta un tiempo límite ($t_0$) [1, 2]. Luego, se le pide pronosticar la sismicidad en la ventana temporal posterior a ese límite [1, 2]. Esto emula de manera segura una prueba en tiempo real sin sesgos geocronológicos [1].

## Fase 8: Medición de la Importancia de Variables (Feature Importance)
Para saber qué indicadores físicos o estadísticos tienen mayor poder predictivo, se aplican técnicas de explicabilidad:
* **Importancia Gini:** Ideal para los modelos de árboles (como Random Forest o GBDT). Mide cuánto contribuye cada variable a reducir la "impureza" en las divisiones de los nodos al clasificar los datos [3].
* **Valores de Shapley (SHAP):** Un enfoque basado en la teoría de juegos cooperativos que calcula la contribución marginal de cada variable en el resultado final [4, 5]. Proporciona una asignación justa de la importancia de las características y mejora drásticamente la transparencia y la interpretabilidad de redes complejas [5, 6].
* **Experimentos de Ablación:** Consiste en eliminar sistemáticamente entradas específicas de tu base de datos (por ejemplo, entrenar el modelo sin la tasa de deformación InSAR o sin el valor *b*) y medir cómo cae el rendimiento [7]. Esto permite identificar rápidamente cuáles variables son absolutamente críticas para el modelo [7].
