# Prompt utilizado

Prompt diseñado para la etapa de análisis, pegado sin cambios al inicio del chat de análisis con Claude.

```
Actuá como analista de datos de negocio. Vas a trabajar sobre un volcado oficial
de la base de datos de osu! (data.ppy.sh, septiembre 2026, modo osu! estándar,
muestra aleatoria de 10.000 jugadores activos).

TABLAS:
- Jugadas por usuario y mapa (6.839.522 registros: user_id, beatmap_id, playcount)
- Mapas (235.046 registros: dificultad, duración, BPM, modo, estado, veces jugado
  y pasado a nivel global)
- Canciones (60.656 registros: artista, género, idioma, favoritos)
- Jugadores (10.000 registros: actividad, país, nivel, tiempo jugado)

ARCHIVOS ADJUNTOS:
Son tablas del volcado original en formato SQL (MySQL), comprimidas con gzip.
La tabla de jugadas está partida en dos: playcount_parte_aa y playcount_parte_ab.
Unilas en ese orden antes de descomprimir. Convertí todo a tablas y confirmá
la cantidad de registros de cada una antes de empezar el análisis.

PREGUNTA DE NEGOCIO:
Para el equipo que decide qué mapas entran al ranking oficial, ¿qué características
de un mapa hacen que los jugadores comunes lo vuelvan a jugar en lugar de abandonarlo?

DEFINICIONES:
- Abandono: el jugador jugó el mapa una sola vez y no volvió.
- Rejuego: el jugador jugó el mapa dos veces o más.
- Jugadores comunes: excluí al 10% más activo de la muestra (según su cantidad
  total de jugadas) y mostrá los resultados de ese 10% aparte, como comparación.
- Solo considerá mapas jugados por al menos 30 jugadores de la muestra.

TAREAS (seguí CRISP-DM):
1. Preparación: filtrá solo mapas del modo osu! estándar, detectá nulos, duplicados
   y valores extremos, y explicá cada decisión de limpieza.
2. KPIs:
   - Tasa de rejuego: % de jugadores de la muestra que jugaron el mapa más de una vez.
   - Tasa de aprobación: pasadas / intentos del mapa (dato global de osu!, no de
     la muestra; aclaralo siempre que lo uses).
   - Concentración del juego: qué % de las jugadas se lleva el top 10% de los mapas.
3. Análisis: compará esos KPIs por rangos de dificultad, duración, BPM, género y
   estado del mapa (rankeado o loved). Los géneros e idiomas vienen como códigos
   numéricos: no inventes sus nombres; si no tenés la equivalencia oficial, pedímela.
4. Validación: para cada hallazgo, mostrame el número exacto y cómo calcularlo, para
   que yo lo verifique por mi cuenta en Google Sheets con una muestra.
5. Dashboard: un archivo HTML único e interactivo con los KPIs y filtros por
   dificultad, duración y género, que aclare que es una foto de los datos de
   septiembre 2026 y no se actualiza sola.
6. Informe ejecutivo: borrador de máximo 2 páginas con estas secciones:
   contexto y problema de negocio; fuente, calidad y preparación de datos;
   KPIs utilizados; 3 hallazgos principales; 3 recomendaciones accionables;
   limitaciones, sesgos y riesgos.

ESTADÍSTICA DESCRIPTIVA:
- Las distribuciones de jugadas están muy sesgadas: usá mediana y percentiles
  (25, 75, 90) como medidas principales. Mostrá la media solo como comparación,
  explicando por qué difiere de la mediana.
- En cada comparación entre grupos, indicá cuántos mapas y jugadores hay en
  cada grupo.
- Para las tasas por grupo, calculá intervalos de confianza del 95% y decime
  si las diferencias entre grupos son claras o podrían ser casualidad.
- Para relaciones entre variables, usá correlación de Spearman y explicá en
  palabras simples qué significa cada resultado.

FORMA DE TRABAJO:
- Hacé una etapa por vez y frená al terminar cada una para que yo la revise
  antes de seguir.

REGLAS:
- No inventes datos ni completes con supuestos: si algo no se puede responder
  con estas tablas, decilo.
- Distinguí correlación de causalidad.
- Nombrá los sesgos de la muestra (solo jugadores activos, solo mapas oficiales).
- Usá lenguaje simple, sin jerga técnica innecesaria.
```
