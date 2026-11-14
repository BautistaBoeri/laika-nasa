"""
Rol Tierra, pasos 4 a 9: máscara, similitud, mejores sitios, validación y
exportación. Corre en local sobre lo que bajó medir.py, así que cambiar pesos,
umbrales o sitios objetivo no gasta cuota de Earth Engine.

Lee:
  earth/datos/<region>/           (de medir.py)
  mars/targets.json               (de Marte)
  content/known_analogs.json      (de Contenido)
Si alguno de los dos JSON no existe todavía, usa el de earth/ejemplo/ y avisa.

Escribe:
  web/data/sites.json
  web/data/similarity_<target>.png     (Web Mercator, para superponer en el mapa)
  earth/parametros_usados.json

Uso:
  python earth/puntuar.py --region noa
  python earth/puntuar.py --region mundo
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

import config as C

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
R_TIERRA_KM = 6371.0


# ------------------------------------------------------------------ Entradas

def elegir_archivo(real, ejemplo):
    if real.exists():
        return real, False
    print(f"AVISO: no existe {real.relative_to(RAIZ)}; uso el ejemplo "
          f"{ejemplo.relative_to(RAIZ)} (valores inventados, solo para probar)")
    return ejemplo, True


def todas():
    """Variables que puntúan más las informativas (se muestran, pero con peso 0)."""
    return C.VARIABLES + [v for v in C.INFORMATIVAS if v not in C.VARIABLES]


def leer_targets(ruta):
    """
    Formato que entrega el rol Marte:
      {"targets": [{"id": "jezero", "name": "...", "lat": 18.4, "lon": 77.5,
                    "values": {"slope": {"mean": 2.66, "std": 2.24}, ...}}, ...],
       "mars_global": {"slope": {"mean": 1.81, "std": 2.55}, ...}}
    C.NOMBRE_EN_MARTE traduce nuestras variables a los nombres de ese archivo.
    Se compara contra el "mean" del sitio; la tolerancia es el "std" global de Marte.
    """
    j = json.loads(ruta.read_text(encoding="utf-8"))
    try:
        sigma = {v: float(C.SIGMA_PROPIA.get(
                     v, j["mars_global"][C.NOMBRE_EN_MARTE[v]]["std"]))
                 for v in todas()}
        targets = []
        for t in j["targets"]:
            valores = {v: float(t["values"][C.NOMBRE_EN_MARTE[v]]["mean"])
                       for v in todas()}
            targets.append({**t, "values": valores})
    except (KeyError, TypeError) as e:
        raise SystemExit(
            f"{ruta} no tiene el formato esperado (falta {e}). "
            "Mirá el comentario de leer_targets() en earth/puntuar.py.") from e
    return targets, sigma


def leer_conocidos(ruta):
    """Formato esperado: [{"name": "...", "lat": -24.1, "lon": -69.9}, ...]"""
    j = json.loads(ruta.read_text(encoding="utf-8"))
    if isinstance(j, dict):
        j = j.get("analogs", j.get("sites", []))
    return [a for a in j if "lat" in a and "lon" in a]


def cargar_datos(region):
    carpeta = AQUI / "datos" / region
    if not (carpeta / "meta.json").exists():
        raise SystemExit(f"No hay datos en {carpeta}. Corré antes: "
                         f"python earth/medir.py --region {region}")
    meta = json.loads((carpeta / "meta.json").read_text(encoding="utf-8"))
    datos = {b: np.load(carpeta / f"{b}.npy", mmap_mode="r") for b in meta["bandas"]}

    # Segunda pasada (medir_extra.py): desvio_m y temperaturas, en la misma grilla.
    extra = AQUI / "datos" / f"{region}_extra"
    if (extra / "meta.json").exists():
        meta_x = json.loads((extra / "meta.json").read_text(encoding="utf-8"))
        if meta_x["forma"] != meta["forma"] or meta_x["bbox"] != meta["bbox"]:
            raise SystemExit(f"{extra} no tiene la misma grilla que {carpeta}")
        for b in meta_x["bandas"]:
            datos[b] = np.load(extra / f"{b}.npy", mmap_mode="r")
        meta["extra"] = meta_x

    faltan = [v for v in todas() if v not in datos and v != "termica"]
    if "termica" in todas():
        faltan += [b for b in ("temp_dia_C", "temp_noche_C") if b not in datos]
    if faltan:
        raise SystemExit(f"Faltan datos de {', '.join(faltan)} para la región {region}. "
                         f"Corré antes: python earth/medir_extra.py --region {region}")
    return meta, datos


def percentil_termico(datos, meta, mascara):
    """
    Inercia térmica aparente = (1 - albedo) / (LST día - LST noche), convertida a
    percentil (0 a 1, ponderado por área) dentro del SUELO DESNUDO: las celdas que
    pasan la máscara. Marte entrega "thermal" igual: el percentil de su inercia
    térmica dentro de Marte, donde todo es suelo desnudo.
    Se probó calcularlo sobre toda la tierra firme y no sirve: la vegetación y la
    humedad ocupan toda la parte alta y los desiertos quedan entre 0,02 y 0,21
    (ver earth/analisis_termica.json).
    Devuelve una grilla con NaN donde no hay dato.
    """
    albedo = np.asarray(datos["albedo"], dtype=np.float64)
    amplitud = (np.asarray(datos["temp_dia_C"], dtype=np.float64)
                - np.asarray(datos["temp_noche_C"], dtype=np.float64))
    with np.errstate(invalid="ignore"):
        ok = mascara & np.isfinite(amplitud) & (amplitud >= C.TERMICA_AMPLITUD_MIN_C)
    filas, cols = np.nonzero(ok)
    ati = (1.0 - albedo[filas, cols]) / amplitud[filas, cols]
    lat = meta["bbox"][3] - (filas + 0.5) * meta["celda_grados"]
    area = np.cos(np.radians(lat))
    orden = np.argsort(ati, kind="stable")
    acumulada = np.cumsum(area[orden])
    pct = np.empty(ati.size)
    pct[orden] = acumulada / acumulada[-1]
    grilla = np.full(albedo.shape, np.nan, np.float32)
    grilla[filas, cols] = pct
    print(f"Térmica: percentil calculado sobre {ati.size} celdas de suelo desnudo "
          f"({int(mascara.sum()) - ati.size} sin temperatura)")
    return grilla


# ------------------------------------------------------------------ Cálculos

def distancia_km(lat, lon, lats, lons):
    p1, p2 = np.radians(lat), np.radians(lats)
    dlat, dlon = p2 - p1, np.radians(lons - lon)
    a = np.sin(dlat / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlon / 2) ** 2
    return 2 * R_TIERRA_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def armar_mascara(datos):
    m = np.ones(datos[C.VARIABLES[0]].shape, bool)
    for v in C.VARIABLES:
        if v in datos:          # las derivadas (térmica) se calculan después
            m &= np.isfinite(datos[v])
    # MODIS deja valores de relleno (p. ej. -32.767) donde no hay medición.
    for banda, (lo, hi) in C.RANGOS_VALIDOS.items():
        valores = np.asarray(datos[banda])
        m &= (valores >= lo) & (valores <= hi)
    m &= np.asarray(datos["ndvi"]) < C.NDVI_MAX
    criterios = [("frac_agua", C.AGUA_MAX)]
    if C.EXCLUIR_HIELO:
        criterios.append(("frac_hielo", C.HIELO_MAX))
    for banda, maximo in criterios:
        valores = np.asarray(datos[banda])
        if not np.isfinite(valores).any():
            print(f"AVISO: {banda} no tiene datos; la máscara NO está filtrando "
                  f"por {banda.split('_')[1]}. Hay que arreglarlo antes de entregar.")
            continue
        m &= valores < maximo
    return m


def similitud(valores, target, sigma):
    """valores: {variable: vector}. Devuelve (total, {variable: parcial})."""
    parciales = {
        v: np.exp(-0.5 * ((valores[v] - target["values"][v]) / sigma[v]) ** 2)
        for v in C.VARIABLES
    }
    return ponderar(parciales), parciales


def ponderar(parciales):
    peso_total = sum(C.PESOS[v] for v in C.VARIABLES)
    total = sum(C.PESOS[v] * parciales[v] for v in C.VARIABLES) / peso_total
    return total.astype(np.float32)


class Circulo:
    """
    Promedios en un círculo de radio_km alrededor de cada celda válida, para
    comparar región contra región (Marte describe cada sitio con un círculo así).
    El círculo se arma fila por fila: en cada fila entra un tramo de columnas cuyo
    ancho depende de la latitud, y se suma con acumuladas. No cruza el meridiano 180.
    """

    def __init__(self, filas, cols, lats, forma, celda, radio_km):
        self.filas, self.cols, self.forma = filas, cols, forma
        alto, ancho = forma
        km_fila = np.radians(celda) * R_TIERRA_KM
        km_col = km_fila * np.cos(np.radians(lats))
        self.tramos = []
        self.n = np.zeros(filas.size)          # celdas del círculo, válidas o no
        alcance = int(radio_km // km_fila)
        for df in range(-alcance, alcance + 1):
            medio = np.floor(np.sqrt(radio_km ** 2 - (df * km_fila) ** 2) / km_col).astype(int)
            f = filas + df
            self.tramos.append((np.clip(f, 0, alto - 1),
                                np.clip(cols - medio, 0, ancho),
                                np.clip(cols + medio + 1, 0, ancho),
                                (f >= 0) & (f < alto)))
            self.n += 2 * medio + 1
        self.validas = self._suma(np.ones(filas.size))
        self.frac_valida = self.validas / self.n

    def _suma(self, vector):
        alto, ancho = self.forma
        g = np.zeros((alto, ancho + 1))
        g[self.filas, self.cols + 1] = vector
        np.cumsum(g, axis=1, out=g)
        s = np.zeros(self.filas.size)
        for f, a, b, dentro in self.tramos:
            s += np.where(dentro, g[f, b] - g[f, a], 0.0)
        return s

    def media_con_ceros(self, vector):
        """Promedio sobre todo el círculo; lo enmascarado cuenta como 0 (puntajes)."""
        return self._suma(vector) / self.n

    def media_finitas(self, vector):
        """Promedio de las celdas del círculo que tienen dato (NaN si ninguna tiene)."""
        ok = np.isfinite(vector)
        n = self._suma(ok.astype(np.float64))
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(n > 0, self._suma(np.where(ok, vector, 0.0)) / n, np.nan)

    def media_validas(self, vector):
        """Promedio solo sobre las celdas válidas del círculo (valores medidos)."""
        return self._suma(vector) / self.validas


def elegir_sitios(total, lats, lons, disponibles):
    """Los N de mayor puntaje, separados al menos SEPARACION_KM entre sí."""
    puntaje = np.where(disponibles, total, -1.0)
    elegidos = []
    while len(elegidos) < C.N_SITIOS:
        i = int(np.argmax(puntaje))
        if puntaje[i] < 0:
            break
        elegidos.append(i)
        puntaje[distancia_km(lats[i], lons[i], lats, lons) < C.SEPARACION_KM] = -1.0
    return elegidos


# -------------------------------------------------------------------- Salidas

PALETA = np.array([[68, 1, 84], [59, 82, 139], [33, 145, 140],
                   [94, 201, 98], [253, 231, 37]], np.float32)


def en_lienzo_del_contrato(grilla, bbox):
    """Ubica la grilla de la región dentro de C.PNG_LIMITES (el resto queda sin dato)."""
    c = C.CELDA_GRADOS
    oeste, sur, este, norte = C.PNG_LIMITES
    alto, ancho = int(round((norte - sur) / c)), int(round((este - oeste) / c))
    lienzo = np.full((alto, ancho), np.nan, np.float32)
    f0 = int(round((norte - bbox[3]) / c))     # fila del lienzo donde cae la fila 0
    k0 = int(round((bbox[0] - oeste) / c))
    fa, ka = max(f0, 0), max(k0, 0)
    fb = min(f0 + grilla.shape[0], alto)
    kb = min(k0 + grilla.shape[1], ancho)
    lienzo[fa:fb, ka:kb] = grilla[fa - f0:fb - f0, ka - k0:kb - k0]
    return lienzo, [oeste, sur, este, norte]


def exportar_png(grilla, bbox, ruta):
    """
    Capa de similitud en Web Mercator (EPSG:3857) con los límites del contrato:
    longitud -180 a 180, latitud -85 a 85, transparente donde no hay dato.
    Devuelve los límites [[S, O], [N, E]].
    """
    grilla, bbox = en_lienzo_del_contrato(grilla, bbox)
    c = C.CELDA_GRADOS
    paso = max(1, int(np.ceil(grilla.shape[1] / C.PNG_ANCHO_MAX)))
    if paso > 1:  # se queda con el máximo de cada bloque para no perder picos
        h = grilla.shape[0] // paso * paso
        w = grilla.shape[1] // paso * paso
        g = np.where(np.isfinite(grilla[:h, :w]), grilla[:h, :w], -1.0)
        g = g.reshape(h // paso, paso, w // paso, paso).max(axis=(1, 3))
        g = np.where(g < 0, np.nan, g)
        norte, este = bbox[3], bbox[0] + w * c
        sur = bbox[3] - h * c
    else:
        g = np.asarray(grilla, dtype=np.float32)
        norte, sur, este = bbox[3], bbox[1], bbox[2]
    oeste = bbox[0]
    celda = c * paso

    def merc(lat):
        return np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))

    norte_m, sur_m = min(norte, 85.0), max(sur, -85.0)
    ancho = g.shape[1]
    alto = max(1, int(round(ancho * (merc(norte_m) - merc(sur_m))
                            / np.radians(este - oeste))))
    ys = merc(norte_m) - (np.arange(alto) + 0.5) * (merc(norte_m) - merc(sur_m)) / alto
    lat_fila = np.degrees(2 * np.arctan(np.exp(ys)) - np.pi / 2)
    filas = np.clip(((norte - lat_fila) / celda).astype(int), 0, g.shape[0] - 1)
    g = g[filas]

    ok = np.isfinite(g)
    s = np.where(ok, g, 0.0)
    pos = np.clip(s, 0, 1) * (len(PALETA) - 1)
    i0 = np.clip(pos.astype(int), 0, len(PALETA) - 2)
    frac = (pos - i0)[..., None]
    rgb = PALETA[i0] * (1 - frac) + PALETA[i0 + 1] * frac
    alfa = np.clip((s - C.PNG_UMBRAL) / max(1 - C.PNG_UMBRAL, 1e-9), 0, 1) * 150 + 80
    alfa = np.where(ok & (s >= C.PNG_UMBRAL), alfa, 0)
    rgba = np.dstack([rgb, alfa]).astype(np.uint8)
    Image.fromarray(rgba, "RGBA").save(ruta, optimize=True)
    return [[round(sur_m, 5), oeste], [round(norte_m, 5), este]]


def redondear(x, n=4):
    return None if x is None or not np.isfinite(x) else round(float(x), n)


def id_sitio(lat, lon):
    """Contrato: latitud y longitud a un decimal unidas con "_" (no depende del ranking)."""
    return f"{round(float(lat), 1) + 0.0:.1f}_{round(float(lon), 1) + 0.0:.1f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="noa")
    args = ap.parse_args()

    meta, datos = cargar_datos(args.region)
    bbox, c = meta["bbox"], meta["celda_grados"]
    alto, ancho = meta["forma"]

    ruta_t, t_ejemplo = elegir_archivo(RAIZ / "mars" / "targets.json",
                                       AQUI / "ejemplo" / "targets.json")
    ruta_c, c_ejemplo = elegir_archivo(RAIZ / "content" / "known_analogs.json",
                                       AQUI / "ejemplo" / "known_analogs.json")
    targets, sigma = leer_targets(ruta_t)
    conocidos = leer_conocidos(ruta_c)

    # Se trabaja solo con las celdas que pasan la máscara.
    mascara = armar_mascara(datos)
    if "termica" in todas():
        datos["termica"] = percentil_termico(datos, meta, mascara)
        if "termica" in C.VARIABLES:      # si puntúa, hace falta el dato en la celda
            mascara &= np.isfinite(datos["termica"])
    idx = np.flatnonzero(mascara)
    if idx.size == 0:
        raise SystemExit("Ninguna celda pasa la máscara. Revisá los umbrales en config.py")
    filas, cols = np.unravel_index(idx, (alto, ancho))
    lats = bbox[3] - (filas + 0.5) * c
    lons = bbox[0] + (cols + 0.5) * c
    valores = {v: np.asarray(datos[v])[filas, cols].astype(np.float64)
               for v in C.VARIABLES}
    # Marte mide "roughness" como desvío estándar; relieve_m es máximo - mínimo.
    if "relieve_m" in valores:
        valores["relieve_m"] = valores["relieve_m"] / C.RELIEVE_A_DESVIO
    # Informativas: se muestran en cada sitio, pero no entran en score ni en ranking.
    informativas = [v for v in C.INFORMATIVAS if v not in C.VARIABLES]
    info = {v: np.asarray(datos[v])[filas, cols].astype(np.float64) for v in informativas}
    info_sitio = info
    elevacion = np.asarray(datos["elevacion_m"])[filas, cols]
    print(f"Región {args.region}: {idx.size} celdas válidas de {alto * ancho} "
          f"({idx.size / (alto * ancho) * 100:.1f}%)")

    # Zona de análogos conocidos: se puntúa, pero no entra en la búsqueda de sitios nuevos.
    libres = np.abs(lats) <= C.LAT_MAX_BUSQUEDA
    cerca = []
    for a in conocidos:
        d = distancia_km(a["lat"], a["lon"], lats, lons)
        libres &= d >= C.RADIO_CONOCIDOS_KM
        cerca.append(d < C.RADIO_VALIDACION_KM)

    # Desempate: cada lugar se describe con el círculo de SUAVIZADO_KM a su alrededor.
    circulo = None
    valores_sitio = valores
    frac_valida = np.ones(idx.size)
    if C.SUAVIZADO_KM > 0:
        circulo = Circulo(filas, cols, lats, (alto, ancho), c, C.SUAVIZADO_KM)
        valores_sitio = {v: circulo.media_validas(valores[v]) for v in C.VARIABLES}
        info_sitio = {v: circulo.media_finitas(info[v]) for v in informativas}
        frac_valida = circulo.frac_valida
        libres &= frac_valida >= C.SUAVIZADO_MIN_FRAC
        print(f"Puntaje promediado en {C.SUAVIZADO_KM} km; sitios nuevos solo donde al "
              f"menos el {C.SUAVIZADO_MIN_FRAC * 100:.0f}% del círculo es válido "
              f"y |lat| <= {C.LAT_MAX_BUSQUEDA}°")

    web = RAIZ / "web" / "data"
    web.mkdir(parents=True, exist_ok=True)
    salida = []

    for t in targets:
        # Dos versiones del puntaje del círculo:
        #   *_val  promedio solo sobre las celdas válidas (análogos conocidos: no se
        #          los castiga por estar rodeados de hielo, agua o vegetación)
        #   total  lo enmascarado cuenta como 0 (ranking de sitios nuevos y capa PNG)
        total, parciales = similitud(valores, t, sigma)
        total_val, parciales_val = total, parciales
        if circulo:
            parciales_val = {v: circulo.media_validas(parciales[v]) for v in C.VARIABLES}
            total_val = ponderar(parciales_val)
            parciales = {v: parciales_val[v] * frac_valida for v in C.VARIABLES}
            total = ponderar(parciales)
        orden, orden_val = np.sort(total), np.sort(total_val)

        # Parecido de las informativas (misma fórmula, promedio de las celdas con dato).
        info_score = {}
        for v in informativas:
            p = np.exp(-0.5 * ((info[v] - t["values"][v]) / sigma[v]) ** 2)
            info_score[v] = circulo.media_finitas(p) if circulo else p

        def ficha(i, rank=None, solo_validas=False, **extra):
            # Campos del contrato primero; rank, percentile, elevation_m y name son extras.
            tot, par, ordn = ((total_val, parciales_val, orden_val) if solo_validas
                              else (total, parciales, orden))
            extra_info = {
                C.NOMBRE_EN_MARTE[v]: {"score": redondear(info_score[v][i]),
                                       "earth": redondear(info_sitio[v][i])}
                for v in informativas if np.isfinite(info_sitio[v][i])}
            return {
                "id": id_sitio(lats[i], lons[i]),
                "lat": redondear(lats[i]), "lon": redondear(lons[i]),
                "known": False,
                "score": redondear(tot[i]),
                "variables": {
                    C.NOMBRE_EN_MARTE[v]: {"score": redondear(par[v][i]),
                                           "earth": redondear(valores_sitio[v][i])}
                    for v in C.VARIABLES} | extra_info,
                "rank": rank,
                "percentile": redondear(np.searchsorted(ordn, tot[i]) / ordn.size * 100, 2),
                "elevation_m": redondear(elevacion[i], 0),
                "valid_frac": redondear(frac_valida[i], 2),
                "name": None, **extra,
            }

        sitios = [ficha(i, r) for r, i in
                  enumerate(elegir_sitios(total, lats, lons, libres), 1)]

        puntuan = {C.NOMBRE_EN_MARTE[v] for v in C.VARIABLES}
        print(f"\n== {t.get('name', t['id'])} ==")
        print("Sitios nuevos:")
        for s in sitios:
            v = s["variables"]
            print(f"  {s['rank']:2d}. {s['lat']:8.3f}, {s['lon']:9.3f}   "
                  f"puntaje {s['score']:.3f}   "
                  + "  ".join(f"{k} {v[k]['score']:.2f}" for k in v if k in puntuan)
                  + "".join(f"  [{k} {v[k]['earth']:.2f}, no puntúa]" for k in v
                            if k not in puntuan)
                  + f"   válido {s['valid_frac'] * 100:.0f}%")

        # El contrato pide score de 0 a 1 en todos los sitios: un conocido que no se
        # pudo puntuar no va en "sites" sino aparte, en "known_unscored".
        sin_puntaje = []
        print("Análogos conocidos (validación):")
        for a, m in zip(conocidos, cerca):
            if m.any():
                i = int(np.flatnonzero(m)[np.argmax(total_val[m])])
                f = ficha(i, solo_validas=True, known=True, name=a["name"])
                aviso = ""
                if abs(a["lat"]) > C.LAT_MAX_BUSQUEDA:
                    f["note"] = (f"Latitud mayor a {C.LAT_MAX_BUSQUEDA}°: el relieve está "
                                 "subestimado por el ancho de la celda")
                    aviso = "  [relieve subestimado por latitud]"
                print(f"  {a['name']:28s} puntaje {f['score']:.3f}  "
                      f"(mejor que el {f['percentile']:.1f}% de las celdas)  "
                      f"válido {f['valid_frac'] * 100:.0f}%{aviso}")
                sitios.append(f)
            else:
                dentro = (bbox[0] <= a["lon"] <= bbox[2]) and (bbox[1] <= a["lat"] <= bbox[3])
                motivo = "enmascarado" if dentro else "fuera de la región"
                sin_puntaje.append({"name": a["name"], "lat": a["lat"], "lon": a["lon"],
                                    "note": motivo})
                print(f"  {a['name']:28s} sin puntaje ({motivo})")

        grilla = np.full((alto, ancho), np.nan, np.float32)
        grilla[filas, cols] = total          # el mismo puntaje que ordena el ranking
        archivo = f"similarity_{t['id']}.png"
        limites = exportar_png(grilla, bbox, web / archivo)

        salida.append({
            "id": t["id"], "name": t.get("name", t["id"]),
            "lat": t.get("lat"), "lon": t.get("lon"),
            "values": {C.NOMBRE_EN_MARTE[v]: t["values"][v] for v in todas()},
            "layer": f"data/{archivo}",
            "sites": sitios,
            "known_unscored": sin_puntaje,
        })

    generado = datetime.now().astimezone().isoformat(timespec="seconds")
    (web / "sites.json").write_text(json.dumps({
        "generated": generado,
        # "informative": true = la variable se muestra pero no entra en el score.
        "variables": [{"id": C.NOMBRE_EN_MARTE[v], "label": C.ETIQUETAS[v][0],
                       "unit": C.ETIQUETAS[v][1]} for v in C.VARIABLES]
                     + [{"id": C.NOMBRE_EN_MARTE[v], "label": C.ETIQUETAS[v][0],
                         "unit": C.ETIQUETAS[v][1], "informative": True}
                        for v in informativas],
        "targets": salida,
        # Lo que sigue no está en el contrato; la página puede ignorarlo.
        "region": args.region,
        "provisional": bool(t_ejemplo or c_ejemplo),
        "weights": {C.NOMBRE_EN_MARTE[v]: (C.PESOS[v] if v in C.VARIABLES else 0.0)
                    for v in todas()},
        "sigma": {C.NOMBRE_EN_MARTE[v]: sigma[v] for v in todas()},
        "layer_bounds": limites,
        "smoothing_km": C.SUAVIZADO_KM,
        "roughness_from_range_factor": C.RELIEVE_A_DESVIO,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    parametros = {k: getattr(C, k) for k in dir(C) if k.isupper()}
    parametros.update({"generado": generado, "region": args.region,
                       "targets": str(ruta_t.relative_to(RAIZ)),
                       "targets_origen": "ejemplo" if t_ejemplo else C.TARGETS_ORIGEN,
                       "targets_sha256": hashlib.sha256(
                           ruta_t.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
                       "conocidos": str(ruta_c.relative_to(RAIZ)),
                       "conocidos_cantidad": len(conocidos),
                       "conocidos_sha256": hashlib.sha256(
                           ruta_c.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
                       "sigma": sigma, "medicion": meta})
    analisis = AQUI / "analisis_termica.json"     # pruebas hechas con la térmica
    if analisis.exists():
        parametros["analisis_termica"] = json.loads(analisis.read_text(encoding="utf-8"))
    (AQUI / "parametros_usados.json").write_text(
        json.dumps(parametros, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nGuardado web/data/sites.json y {len(salida)} capa(s) PNG en web/data/")
    if t_ejemplo or c_ejemplo:
        print("OJO: se usaron archivos de ejemplo; el resultado es solo para probar.")


if __name__ == "__main__":
    main()
