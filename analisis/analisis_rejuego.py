"""
Análisis de rejuego en mapas de osu! (modo estándar)
=====================================================

Pregunta de negocio: para el equipo que decide qué mapas entran al ranking
oficial, ¿qué características de un mapa hacen que los jugadores comunes lo
vuelvan a jugar (≥2 jugadas) en vez de abandonarlo (1 sola jugada)?

Datos: volcado oficial de data.ppy.sh, muestra random_10000, modo osu!
estándar, septiembre 2026. Hay que descargarlo y descomprimirlo aparte (pesa
~1 GB y no se sube al repo).

Uso:
    pip install pandas numpy scipy
    python analisis_rejuego.py --datos /ruta/a/la/carpeta/descomprimida

Salida: carpeta resultados/ con las tablas en CSV, los dos CSV de validación
humana y, al final, un chequeo que compara los números clave contra los
publicados en el informe.

Nota sobre el origen: este script reconstruye el pipeline a partir de las
decisiones documentadas en evidencia/. El análisis original se ejecutó con
Claude en scripts por etapa. El bloque final de verificación existe justamente
para comprobar que esta versión reproduce los resultados publicados.
"""

import argparse
import csv
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

SEMILLA = 42
N_BOOTSTRAP = 1000
MIN_JUGADORES = 30          # mínimo de jugadores por grupo para medir un mapa
N_TOP = 1000                # top 10% de los 10.000 jugadores de la muestra
DIF_RELEVANTE = 2.0         # diferencias < 2 puntos no cambian decisiones

ESTADOS_OFICIALES = [1, 2, 4]   # rankeado, aprobado, loved (sin qualified)

# Códigos oficiales de la API v1 de osu! (github.com/ppy/osu-api/wiki)
GENEROS = {2: "Videojuego", 3: "Anime", 4: "Rock", 5: "Pop", 6: "Otro",
           7: "Novelty", 9: "Hip hop", 10: "Electrónica", 11: "Metal",
           12: "Clásica", 13: "Folk", 14: "Jazz"}

# Resultados publicados en el informe, para el chequeo final
ESPERADO = {
    "jugadores_muestra": 10_000,
    "umbral_top10_jugadas": 13_494,
    "mapas_con_30_en_ambos_grupos": 12_893,
    "pico_rejuego_comunes_4_5_estrellas_pct": 69.8,
    "mapas_cuadrante_b_rejuego_alto_aprob_baja": 4_533,
    "mapas_mas_dificiles_que_sus_estrellas": 1_146,
}


# ---------------------------------------------------------------------------
# ETAPA 0 · Carga: de volcado SQL de MySQL a DataFrame
# ---------------------------------------------------------------------------

def leer_volcado_sql(ruta: Path) -> pd.DataFrame:
    """Lee un volcado de mysqldump (CREATE TABLE + INSERT ... VALUES)."""
    columnas, filas = [], []
    en_create = False
    sentencia = None            # INSERT en curso (puede ocupar varias líneas)
    with open(ruta, encoding="utf-8", errors="replace") as f:
        for linea in f:
            if sentencia is not None:
                sentencia += linea
            elif linea.startswith("CREATE TABLE"):
                en_create = True
                continue
            elif en_create:
                m = re.match(r"\s+`(\w+)`", linea)
                if m:
                    columnas.append(m.group(1))
                elif linea.startswith(")"):
                    en_create = False
                continue
            elif linea.startswith("INSERT INTO"):
                sentencia = linea
            else:
                continue
            if not sentencia.rstrip().endswith(";"):
                continue                     # la fila sigue en la próxima línea
            valores = sentencia.split(" VALUES ", 1)[1]
            sentencia = None
            # Cada fila es un (...) cuyo interior puede tener textos entre
            # comillas con paréntesis y comas adentro (títulos de canciones).
            # MySQL 8 antepone _binary a algunos textos: se quita para que el
            # texto vuelva a empezar con comilla.
            tuplas = [INTRODUCTOR.sub("'", t) for t in TUPLA_SQL.findall(valores)]
            lector = csv.reader(tuplas, quotechar="'", escapechar="\\",
                                doublequote=False)
            filas.extend(lector)
    malas = [f for f in filas if len(f) != len(columnas)]
    if malas:
        largos = pd.Series([len(f) for f in malas]).value_counts().to_dict()
        sys.exit(f"{ruta.name}: {len(malas)} filas no tienen {len(columnas)} columnas "
                 f"(largos encontrados: {largos}).\nPrimera fila con problema:\n"
                 + "\n".join(f"  {i:>2} {c!r}" for i, c in enumerate(malas[0])))
    df = pd.DataFrame(filas, columns=columnas)
    return df.replace("NULL", np.nan)


# Una fila de un INSERT: paréntesis que contienen textos entre comillas
# (con escapes \' o \\) o cualquier cosa que no sea comilla ni paréntesis
TUPLA_SQL = re.compile(r"\(((?:'(?:[^'\\]|\\.)*'|[^'()])*)\)", re.DOTALL)
INTRODUCTOR = re.compile(r"\b_(?:binary|utf8mb4|utf8|latin1)\s*'")


def a_numero(df: pd.DataFrame, cols) -> pd.DataFrame:
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def cargar(carpeta: Path):
    def buscar(nombre):
        rutas = list(carpeta.rglob(f"{nombre}.sql"))
        if not rutas:
            sys.exit(f"No encontré {nombre}.sql dentro de {carpeta}")
        return rutas[0]

    b = a_numero(leer_volcado_sql(buscar("osu_beatmaps")),
                 ["beatmap_id", "beatmapset_id", "playmode", "approved",
                  "difficultyrating", "total_length", "bpm", "passcount", "playcount"])
    s = a_numero(leer_volcado_sql(buscar("osu_beatmapsets")),
                 ["beatmapset_id", "favourite_count", "play_count", "genre_id", "language_id"])
    p = a_numero(leer_volcado_sql(buscar("osu_user_beatmap_playcount")),
                 ["user_id", "beatmap_id", "playcount"])
    st = a_numero(leer_volcado_sql(buscar("osu_user_stats")), ["user_id", "playcount"])

    print("ETAPA 0 · Registros cargados")
    for nombre, df in [("osu_beatmaps", b), ("osu_beatmapsets", s),
                       ("osu_user_beatmap_playcount", p), ("osu_user_stats", st)]:
        print(f"  {nombre:<28} {len(df):>10,}")
    return b, s, p, st


# ---------------------------------------------------------------------------
# ETAPA 1 · Preparación: filtros, grupos y umbral de 30 jugadores
# ---------------------------------------------------------------------------

def preparar(b, s, p, st):
    mapas = b[(b.playmode == 0) & (b.approved.isin(ESTADOS_OFICIALES))].copy()
    jugadas = p[p.beatmap_id.isin(mapas.beatmap_id) & (p.playcount > 0)].copy()

    # Top 10%: los 1.000 jugadores con más jugadas en mapas oficiales de estándar
    total = jugadas.groupby("user_id").playcount.sum().sort_values(ascending=False)
    top = set(total.index[:N_TOP])
    umbral = int(total.iloc[N_TOP - 1])
    jugadas["grupo"] = np.where(jugadas.user_id.isin(top), "top10", "comun")
    jugadas["rejuego"] = (jugadas.playcount >= 2).astype(int)

    # Jugadores y tasa de rejuego por mapa y grupo
    por_mapa = (jugadas.groupby(["beatmap_id", "grupo"])
                .agg(jugadores=("user_id", "nunique"), tasa=("rejuego", "mean"))
                .unstack("grupo"))
    por_mapa.columns = [f"{m}_{g}" for m, g in por_mapa.columns]
    mapas = mapas.join(por_mapa, on="beatmap_id")
    mapas[["jugadores_comun", "jugadores_top10"]] = (
        mapas[["jugadores_comun", "jugadores_top10"]].fillna(0))

    # Atributos derivados
    mapas = mapas.merge(s[["beatmapset_id", "favourite_count", "play_count",
                           "genre_id", "artist", "title"]],
                        on="beatmapset_id", how="left")
    mapas["aprobacion"] = mapas.passcount / mapas.playcount
    mapas["estado"] = np.where(mapas.approved == 4, "Loved", "Rankeado")
    mapas["genero"] = mapas.genre_id.map(GENEROS)
    mapas["r_dif"] = pd.cut(mapas.difficultyrating, [0.0001, 2, 3, 4, 5, 6, 7, 8, 1e9],
                            right=False,
                            labels=["<2★", "2–3★", "3–4★", "4–5★", "5–6★", "6–7★", "7–8★", "8★+"])
    mapas["r_dur"] = pd.cut(mapas.total_length, [0, 60, 120, 180, 240, 300, 1e9],
                            right=False,
                            labels=["<1 min", "1–2 min", "2–3 min", "3–4 min", "4–5 min", "5 min+"])
    mapas["r_bpm"] = pd.cut(mapas.bpm, [0, 120, 150, 180, 210, 240, 1e9], right=False,
                            labels=["<120", "120–150", "150–180", "180–210", "210–240", "240+"])

    # (La aprobación ajustada se calcula en la etapa 3, sobre los mapas analizados)
    mapas["banda"] = (np.floor(mapas.difficultyrating * 2) / 2).clip(upper=9)

    medibles = mapas[mapas.jugadores_comun >= MIN_JUGADORES]
    sin_estrellas = medibles[medibles.difficultyrating == 0]

    print("\nETAPA 1 · Preparación")
    print(f"  Jugadores con jugadas en mapas oficiales: {len(total):,}")
    print(f"  Umbral top 10% (jugadas del jugador n.º {N_TOP}): {umbral:,}")
    print(f"  Mapas oficiales de estándar: {len(mapas):,}")
    print(f"  Mapas con ≥{MIN_JUGADORES} jugadores comunes: {len(medibles):,}")
    print(f"  De esos, con 0★ (quedan fuera SOLO del análisis por dificultad): "
          f"{len(sin_estrellas)}")
    return mapas, jugadas, umbral


# ---------------------------------------------------------------------------
# ETAPA 2 · KPIs con intervalos de confianza
# ---------------------------------------------------------------------------

def tasa_con_ic(jug: pd.DataFrame):
    """Tasa de rejuego agregada + IC 95% por bootstrap re-muestreando mapas."""
    por_mapa = jug.groupby("beatmap_id").rejuego.agg(["sum", "count"])
    tasa = por_mapa["sum"].sum() / por_mapa["count"].sum()
    rng = np.random.default_rng(SEMILLA)
    idx = rng.integers(0, len(por_mapa), size=(N_BOOTSTRAP, len(por_mapa)))
    sumas, cuentas = por_mapa["sum"].to_numpy(), por_mapa["count"].to_numpy()
    boot = sumas[idx].sum(axis=1) / cuentas[idx].sum(axis=1)
    return 100 * tasa, 100 * np.percentile(boot, 2.5), 100 * np.percentile(boot, 97.5)


def rejuego_por(variable, grupo, mapas, jugadas, ids):
    datos = jugadas[(jugadas.grupo == grupo) & jugadas.beatmap_id.isin(ids)]
    datos = datos.merge(mapas[["beatmap_id", variable]], on="beatmap_id")
    filas = []
    for cat, sub in datos.groupby(variable, observed=True):
        tasa, lo, hi = tasa_con_ic(sub)
        filas.append({variable: cat, "grupo": grupo, "mapas": sub.beatmap_id.nunique(),
                      "tasa_rejuego": round(tasa, 1),
                      "ic95_inf": round(lo, 1), "ic95_sup": round(hi, 1)})
    return pd.DataFrame(filas)


# ---------------------------------------------------------------------------
# ETAPA 3 · Análisis comparativo
# ---------------------------------------------------------------------------

def analizar(mapas, jugadas, salida: Path):
    medibles = mapas[mapas.jugadores_comun >= MIN_JUGADORES]
    con_estrellas = medibles[medibles.difficultyrating > 0].copy()
    # Aprobación ajustada: cada mapa contra la mediana de su banda de 0,5★,
    # calculada dentro de los mapas analizados (no de todo el catálogo)
    con_estrellas["aprob_ajustada"] = (
        con_estrellas.aprobacion /
        con_estrellas.groupby("banda").aprobacion.transform("median"))
    ambos = mapas[(mapas.jugadores_comun >= MIN_JUGADORES) &
                  (mapas.jugadores_top10 >= MIN_JUGADORES) &
                  (mapas.difficultyrating > 0)]

    # 1. Curva de rejuego por dificultad (comunes)
    curva = rejuego_por("r_dif", "comun", mapas, jugadas, con_estrellas.beatmap_id)
    curva.to_csv(salida / "rejuego_por_dificultad_comunes.csv", index=False)
    print("\nETAPA 3 · Rejuego de jugadores comunes por dificultad")
    print(curva.to_string(index=False))

    # 2. Comunes vs top 10%, solo en mapas con ≥30 jugadores en ambos grupos
    comp = pd.concat([rejuego_por("r_dif", g, mapas, jugadas, ambos.beatmap_id)
                      for g in ["comun", "top10"]])
    comp = comp.pivot(index="r_dif", columns="grupo", values="tasa_rejuego")
    comp = comp.reindex([c for c in mapas.r_dif.cat.categories if c in comp.index])
    comp["diferencia"] = comp["comun"] - comp["top10"]
    comp["relevante"] = comp["diferencia"].abs() >= DIF_RELEVANTE
    comp.to_csv(salida / "comunes_vs_top10_por_dificultad.csv")
    print(f"\n  Comunes vs top 10% ({len(ambos):,} mapas con ≥{MIN_JUGADORES} en ambos)")
    print(comp.round(1).to_string())

    # 3. Duración controlando por dificultad
    dur = []
    for r, sub in con_estrellas.groupby("r_dif", observed=True):
        t = rejuego_por("r_dur", "comun", mapas, jugadas, sub.beatmap_id)
        t.insert(0, "r_dif", r)
        dur.append(t)
    pd.concat(dur).to_csv(salida / "rejuego_por_duracion_dentro_de_dificultad.csv", index=False)

    # 4. BPM, género y estado
    for var in ["r_bpm", "genero", "estado"]:
        rejuego_por(var, "comun", mapas, jugadas, con_estrellas.beatmap_id).to_csv(
            salida / f"rejuego_por_{var.replace('r_', '')}.csv", index=False)

    # 5. Correlaciones de Spearman (nivel mapa)
    corr = []
    for var in ["difficultyrating", "total_length", "bpm", "aprob_ajustada"]:
        x = con_estrellas[["tasa_comun", var]].dropna()
        rho, pval = spearmanr(x["tasa_comun"], x[var])
        corr.append({"variable": var, "rho": round(rho, 3), "p_valor": pval, "n": len(x)})
    pd.DataFrame(corr).to_csv(salida / "correlaciones_spearman.csv", index=False)
    print("\n  Spearman: tasa de rejuego de comunes vs. atributos del mapa")
    print(pd.DataFrame(corr).to_string(index=False))

    # 6. Cuadrantes: rejuego (corte en la mediana) × aprobación ajustada (corte en 1,0).
    #    El cuadrante B (rejuego alto + aprobación ajustada baja) se lee como
    #    mapas que resultan más difíciles de lo que indican sus estrellas.
    mediana = con_estrellas.tasa_comun.median()
    cuadrante_b = con_estrellas[(con_estrellas.tasa_comun >= mediana) &
                                (con_estrellas.aprob_ajustada < 1)]
    #    Versión marcada: rejuego en el cuartil superior y aprobación ≤ 0,75
    #    de lo esperado para sus estrellas.
    p75 = con_estrellas.tasa_comun.quantile(0.75)
    dificiles = con_estrellas[(con_estrellas.tasa_comun >= p75) &
                              (con_estrellas.aprob_ajustada <= 0.75)]
    dificiles[["beatmap_id", "artist", "title", "version", "difficultyrating",
               "jugadores_comun", "tasa_comun", "aprobacion", "aprob_ajustada"]].sort_values(
        "aprob_ajustada").to_csv(salida / "mapas_mas_dificiles_que_sus_estrellas.csv", index=False)
    print(f"\n  Cuadrante B (rejuego ≥ mediana {100 * mediana:.1f}% y aprobación ajustada < 1): "
          f"{len(cuadrante_b):,}")
    print(f"  Versión marcada (rejuego ≥ p75 {100 * p75:.1f}% y aprobación ajustada ≤ 0,75): "
          f"{len(dificiles):,}")

    return {"ambos": len(ambos), "curva": curva, "cuadrante_b": len(cuadrante_b),
            "dificiles": len(dificiles)}


# ---------------------------------------------------------------------------
# ETAPA 4 · Exportes para validación humana en Excel
# ---------------------------------------------------------------------------

def exportar_validacion(mapas, jugadas, salida: Path):
    # Validación 1: filas crudas de un mapa puntual para recalcular a mano
    rock = mapas[mapas.title.str.contains("Rockefeller Street", case=False, na=False) &
                 (mapas.jugadores_comun >= MIN_JUGADORES)]
    (jugadas[(jugadas.grupo == "comun") & jugadas.beatmap_id.isin(rock.beatmap_id)]
     [["beatmap_id", "user_id", "playcount", "rejuego"]]
     .to_csv(salida / "validacion_1_rockefeller_street.csv", index=False))

    # Validación 2: 500 mapas al azar para reproducir la curva en Excel
    muestra = mapas[(mapas.jugadores_comun >= MIN_JUGADORES) &
                    (mapas.difficultyrating > 0)].sample(500, random_state=SEMILLA)
    (muestra[["beatmap_id", "title", "version", "difficultyrating", "r_dif",
              "jugadores_comun", "tasa_comun"]]
     .to_csv(salida / "validacion_2_muestra_500_mapas.csv", index=False))


# ---------------------------------------------------------------------------
# Chequeo final contra el informe publicado
# ---------------------------------------------------------------------------

def verificar(obtenido: dict):
    print("\nVERIFICACIÓN contra el informe publicado")
    todo_ok = True
    for clave, esperado in ESPERADO.items():
        real = obtenido.get(clave)
        ok = real is not None and abs(float(real) - float(esperado)) < 0.05
        todo_ok &= ok
        print(f"  {'OK ' if ok else 'NO '} {clave:<42} esperado={esperado}  obtenido={real}")
    print("\n  Todo coincide." if todo_ok else
          "\n  Hay diferencias: revisar antes de citar estos números.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", required=True, type=Path,
                    help="Carpeta con los .sql descomprimidos de data.ppy.sh")
    ap.add_argument("--salida", default=Path("resultados"), type=Path)
    args = ap.parse_args()
    args.salida.mkdir(exist_ok=True)

    b, s, p, st = cargar(args.datos)
    mapas, jugadas, umbral = preparar(b, s, p, st)
    res = analizar(mapas, jugadas, args.salida)
    exportar_validacion(mapas, jugadas, args.salida)

    pico = res["curva"].loc[res["curva"].r_dif == "4–5★", "tasa_rejuego"]
    verificar({
        "jugadores_muestra": st.user_id.nunique(),
        "umbral_top10_jugadas": umbral,
        "mapas_con_30_en_ambos_grupos": res["ambos"],
        "pico_rejuego_comunes_4_5_estrellas_pct": float(pico.iloc[0]) if len(pico) else None,
        "mapas_cuadrante_b_rejuego_alto_aprob_baja": res["cuadrante_b"],
        "mapas_mas_dificiles_que_sus_estrellas": res["dificiles"],
    })


if __name__ == "__main__":
    main()
