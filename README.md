# osu!: ¿qué mapas se rejuegan?"

Análisis de retención sobre **6,8 millones de jugadas** del juego de ritmo osu!, para responder una pregunta de negocio concreta: qué características de un mapa hacen que los jugadores comunes lo vuelvan a jugar en lugar de abandonarlo.

📊 **[Ver el dashboard interactivo](https://iarabueno.github.io/OSU-REJUEGO-ANALISIS/)**

---

## El problema

En osu!, cada canción jugable es un **mapa** y su dificultad se mide en **estrellas (★)**. El equipo que decide qué mapas entran al ranking oficial necesita saber qué mapas retienen a los jugadores comunes, no solo a los más activos.

- **Rejuego:** el jugador jugó el mapa 2 veces o más.
- **Abandono:** lo jugó una sola vez.
- **Jugadores comunes:** toda la muestra menos el 10% más activo, que se analizó aparte como comparación.

## Los datos

- **Fuente:** volcado oficial de la base de datos de osu! publicado por sus desarrolladores en [data.ppy.sh](https://data.ppy.sh) (`2026_09_01_performance_osu_random_10000`).
- **Muestra:** 10.000 jugadores activos elegidos al azar, modo osu! estándar. Se eligió la muestra aleatoria y no la de los mejores jugadores para evitar el sesgo de supervivencia.
- **Tablas usadas:** 6.839.522 jugadas por jugador y mapa, 235.046 mapas, 60.656 canciones y 10.000 jugadores.

Los datos crudos no se incluyen en este repositorio por su tamaño y su licencia. Se pueden descargar desde la fuente original.

## Cómo se hizo

El trabajo siguió la metodología **CRISP-DM**, con análisis asistido por IA (Claude) y validación humana en cada etapa:

1. **Comprensión de los datos:** descarga del volcado y conteo de registros.
2. **Preparación:** conversión de las tablas SQL, filtro de modo estándar y mapas oficiales, y umbral de al menos 30 jugadores por mapa.
3. **Análisis:** KPIs por dificultad, duración, BPM, género y estado del mapa, con medianas, intervalos de confianza y correlación de Spearman.
4. **Evaluación:** recálculo independiente de los resultados clave en Excel.
5. **Despliegue:** dashboard interactivo e informe ejecutivo.

## KPIs

| KPI | Valor |
|---|---|
| Tasa de rejuego de jugadores comunes | **65,6%** |
| Tasa de aprobación (mediana, dato global de osu!) | **22,0%** |
| Concentración: jugadas que se lleva el 10% de mapas más populares | **71,9%** |

## Hallazgos

1. **La dificultad divide a dos públicos.** Los jugadores comunes rejuegan más los mapas de 4–5★ (69,8%) y por encima de 5★ su rejuego empieza a bajar, mientras que el del 10% más activo sigue subiendo.
2. **Los mapas cortos retienen más,** incluso comparando mapas de igual dificultad: los de menos de 1 minuto tienen 4,8 puntos más de rejuego que lo esperable para sus estrellas.
3. **1.146 mapas son más difíciles de lo que dicen sus estrellas:** se rejuegan mucho pero se pasan mucho menos de lo esperable, y suelen ser más largos.

## Recomendaciones

1. **Cuidar** la oferta de mapas de 3 a 6★, que reúne el 77% de las jugadas de los comunes en los mapas analizados.
2. **Revisar** la lista de 1.146 mapas cuyas estrellas podrían subestimar la dificultad real.
3. **Medir y probar:** registrar jugadas con fecha para separar reintentos de regresos, y probar cambios contra un grupo de control.

## Validación humana

- Recalculé en Excel la tasa de rejuego de un mapa puntual (77,1%) y la curva por estrellas en una muestra aleatoria de 500 mapas. Ambos coincidieron.
- Revisando los resultados detecté decisiones que la IA había tomado sin informar, como un mapa excluido del análisis, y las corregí.
- Corrí el script de `analisis/` en mi computadora desde los datos crudos y reprodujo los seis resultados clave del informe.

## Limitaciones

- El rejuego incluye reintentos inmediatos, no solo regresos días después.
- La aprobación y los favoritos son datos globales de osu!, no de la muestra.
- La muestra solo incluye jugadores activos y mapas oficiales.
- Los resultados muestran asociaciones, no causas.

## Contenido del repositorio

| Carpeta | Contenido |
|---|---|
| Branch `docs` | Dashboard interactivo publicado en GitHub Pages ([ver en línea](https://iarabueno.github.io/OSU-REJUEGO-ANALISIS/)) |
| `informe/` | Informe ejecutivo |
| `evidencia/` | Evidencia del proceso por etapa de CRISP-DM |
| `validacion/` | Planillas de validación en Excel |
| `analisis/` | Script en Python que reproduce el análisis desde el volcado oficial |
| `prompt/` | Prompt utilizado para el análisis |

## Cómo reproducir el análisis

1. Descargar el volcado `2026_09_01_performance_osu_random_10000` de [data.ppy.sh](https://data.ppy.sh) y descomprimir los archivos `.sql`.
2. Instalar las dependencias: `pip install pandas numpy scipy`
3. Correr: `python analisis/analisis_rejuego.py --datos <carpeta con los .sql>`

El script termina con una verificación automática que compara seis resultados clave contra los publicados en el informe: los 10.000 jugadores de la muestra, el umbral del top 10%, los mapas comparados, el pico de rejuego, el cuadrante de rejuego alto con aprobación baja y los 1.146 mapas a revisar. Los seis coinciden.

## Herramientas

Claude (análisis y dashboard) · Python con pandas y SciPy (script reproducible) · Excel / Google Sheets (validación) · Terminal de macOS (descarga y conteo) · HTML + JavaScript (dashboard)

---

**Iara Lourdes Bueno** · Septiembre 2026

