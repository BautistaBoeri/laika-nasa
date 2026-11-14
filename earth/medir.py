"""
Rol Tierra, pasos 2 a 4: mide las variables con Earth Engine y las baja a disco.

Para cada celda de 0.05° calcula:
  elevacion_m     elevación media
  pendiente_deg   pendiente media, calculada sobre el modelo degradado a ~463 m
  relieve_m       máximo - mínimo de la elevación (a ~463 m) dentro de la celda
  albedo          albedo de onda corta (MODIS), mediana de varios años
  ndvi            percentil 90 del NDVI (para la máscara de vegetación)
  frac_agua       fracción de la celda clasificada como agua
  frac_hielo      fracción de la celda clasificada como hielo permanente
Con --tanda2 suma temp_dia_C y temp_noche_C.

Pide la región en tiles, guarda cada tile en earth/cache/ (si se corta, al
volver a correr sigue desde donde quedó) y arma un archivo por variable en
earth/datos/<region>/.

Uso:
  python earth/medir.py --region noa
  python earth/medir.py --region mundo
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import ee
import numpy as np
from PIL import Image

import config as C

AQUI = Path(__file__).resolve().parent
BANDAS = ["elevacion_m", "pendiente_deg", "relieve_m", "albedo", "ndvi",
          "frac_agua", "frac_hielo"]
BANDAS_T2 = ["temp_dia_C", "temp_noche_C"]


# ---------------------------------------------------------------- Earth Engine

def elegir_dem():
    for cid in (C.DEM_COLECCION, C.DEM_RESPALDO):
        try:
            ee.ImageCollection(cid).limit(1).size().getInfo()
            return cid
        except Exception as e:  # noqa: BLE001
            print(f"  aviso: no se pudo abrir {cid} ({str(e)[:80]})")
    raise SystemExit("No se pudo abrir ningún modelo de elevación. Revisá config.py")


def cada_n_dias(col, n):
    col = col.map(lambda i: i.set("k", i.date().getRelative("day", "year").mod(n)))
    return col.filter(ee.Filter.eq("k", 0))


def construir_imagen(dem_id, tanda2):
    d = C.CELDA_GRADOS / C.SUBCELDAS
    fino = [d, 0, -180, 0, -d, 90]            # grilla de ~463 m alineada a la de salida
    max_px = C.SUBCELDAS ** 2 + 112

    def a_celda(img, reducer):
        return img.reduceResolution(reducer=reducer, maxPixels=max_px)

    # Elevación degradada a ~463 m. Earth Engine lee el nivel de pirámide más
    # cercano (promedios de ~250 m) y lo interpola a la grilla fina.
    dem = (
        ee.ImageCollection(dem_id)
        .select(C.DEM_BANDA)
        .map(lambda i: i.resample("bilinear"))
        .mosaic()
        .reproject(crs="EPSG:4326", crsTransform=fino)
    )
    pendiente = ee.Terrain.slope(dem)
    minmax = a_celda(dem, ee.Reducer.minMax())
    relieve = minmax.select(".*_max").subtract(minmax.select(".*_min"))

    anios = ee.Filter.Or(*[
        ee.Filter.date(f"{a}-01-01", f"{a + 1}-01-01") for a in C.ALBEDO_ANIOS
    ])
    albedo = (
        cada_n_dias(ee.ImageCollection("MODIS/061/MCD43A3").filter(anios),
                    C.ALBEDO_CADA_DIAS)
        .select("Albedo_WSA_shortwave")
        .median()               # la mediana descarta la nieve estacional
        .multiply(0.001)
    )

    ndvi = (
        ee.ImageCollection("MODIS/061/MOD13A2")
        .filterDate(C.NDVI_DESDE, C.NDVI_HASTA)
        .select("NDVI")
        .reduce(ee.Reducer.percentile([90]))
        .multiply(0.0001)
    )

    # Cobertura: se lleva primero a la misma grilla fina que la elevación y
    # después se promedia por celda, igual que la pendiente.
    cobertura = (
        ee.ImageCollection("MODIS/061/MCD12Q1")
        .filterDate(f"{C.COBERTURA_ANIO}-01-01", f"{C.COBERTURA_ANIO + 1}-01-01")
        .first()
        .select("LC_Type1")
    )

    def fraccion(clase):
        binaria = cobertura.eq(clase).reproject(crs="EPSG:4326", crsTransform=fino)
        return a_celda(binaria, ee.Reducer.mean())

    frac_agua = fraccion(17)
    frac_hielo = fraccion(15)

    capas = [
        a_celda(dem, ee.Reducer.mean()).rename("elevacion_m"),
        a_celda(pendiente, ee.Reducer.mean()).rename("pendiente_deg"),
        relieve.rename("relieve_m"),
        albedo.rename("albedo"),
        ndvi.rename("ndvi"),
        frac_agua.rename("frac_agua"),
        frac_hielo.rename("frac_hielo"),
    ]
    bandas = list(BANDAS)

    if tanda2:
        lst = ee.ImageCollection("MODIS/061/MOD11A2").filterDate(C.TEMP_DESDE, C.TEMP_HASTA)
        capas.append(lst.select("LST_Day_1km").mean().multiply(0.02).subtract(273.15)
                     .rename("temp_dia_C"))
        capas.append(lst.select("LST_Night_1km").mean().multiply(0.02).subtract(273.15)
                     .rename("temp_noche_C"))
        bandas += BANDAS_T2

    return ee.Image.cat(capas).unmask(C.NODATA).toFloat(), bandas


# ---------------------------------------------------------------------- Tiles

def armar_tiles(bbox):
    """Lista de (lon_oeste, lat_norte, ancho_px, alto_px, fila0, col0)."""
    lon0, lat0, lon1, lat1 = bbox
    c = C.CELDA_GRADOS
    paso = int(round(C.TILE_GRADOS / c))
    ancho = int(round((lon1 - lon0) / c))
    alto = int(round((lat1 - lat0) / c))
    out = []
    for f in range(0, alto, paso):
        for k in range(0, ancho, paso):
            out.append((lon0 + k * c, lat1 - f * c,
                        min(paso, ancho - k), min(paso, alto - f), f, k))
    return out, alto, ancho


def pedir_una(imagen, bandas, lon, lat, w, h):
    c = C.CELDA_GRADOS
    arr = ee.data.computePixels({
        "expression": imagen,
        "fileFormat": "NUMPY_NDARRAY",
        "grid": {
            "dimensions": {"width": w, "height": h},
            "affineTransform": {"scaleX": c, "shearX": 0, "translateX": lon,
                                "shearY": 0, "scaleY": -c, "translateY": lat},
            "crsCode": "EPSG:4326",
        },
    })
    return np.stack([arr[b] for b in bandas]).astype(np.float32)


def pedir(imagen, bandas, lon, lat, w, h, contador):
    """Pide un tile. Reintenta errores pasajeros y parte en 4 si es muy pesado."""
    c = C.CELDA_GRADOS
    for intento in range(5):
        try:
            contador[0] += 1
            return pedir_una(imagen, bandas, lon, lat, w, h)
        except ee.EEException as e:
            msg = str(e).lower()
            if "quota" in msg:
                raise SystemExit(f"Cuota del proyecto agotada: {e}") from e
            pasajero = any(p in msg for p in ("too many requests", "429", "503",
                                              "unavailable", "internal error",
                                              "deadline"))
            pesado = any(p in msg for p in ("memory", "timed out", "too large",
                                            "too many pixels"))
            if pesado and min(w, h) >= 40:
                w1, h1 = w // 2, h // 2
                out = np.empty((len(bandas), h, w), np.float32)
                for (fo, ko, hh, ww) in ((0, 0, h1, w1), (0, w1, h1, w - w1),
                                         (h1, 0, h - h1, w1), (h1, w1, h - h1, w - w1)):
                    out[:, fo:fo + hh, ko:ko + ww] = pedir(
                        imagen, bandas, lon + ko * c, lat - fo * c, ww, hh, contador)
                return out
            if pasajero and intento < 4:
                time.sleep(5 * (intento + 1))
                continue
            raise
    raise RuntimeError("sin respuesta de Earth Engine")


# ------------------------------------------------------------------- Salidas

def vista_previa(arr, ruta):
    """PNG en escala de grises (2%-98%) para mirar que los valores tengan sentido."""
    paso = max(1, int(np.ceil(arr.shape[1] / 2000)))
    a = np.asarray(arr[::paso, ::paso], dtype=np.float32)
    ok = np.isfinite(a)
    if not ok.any():
        return
    lo, hi = np.percentile(a[ok], [2, 98])
    g = np.clip((a - lo) / max(hi - lo, 1e-9), 0, 1)
    g = np.where(ok, g, 0)
    rgba = np.zeros(a.shape + (4,), np.uint8)
    rgba[..., :3] = (g * 255).astype(np.uint8)[..., None]
    rgba[..., 3] = np.where(ok, 255, 0)
    Image.fromarray(rgba, "RGBA").save(ruta)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="noa", choices=sorted(C.REGIONES))
    ap.add_argument("--tanda2", action="store_true", help="suma temperatura")
    ap.add_argument("--rehacer", action="store_true", help="ignora el cache")
    args = ap.parse_args()

    ee.Initialize(project=C.PROYECTO)
    bbox = C.REGIONES[args.region]
    nombre = args.region + ("_t2" if args.tanda2 else "")
    cache = AQUI / "cache" / nombre
    salida = AQUI / "datos" / nombre
    cache.mkdir(parents=True, exist_ok=True)
    salida.mkdir(parents=True, exist_ok=True)

    dem_id = elegir_dem()
    print(f"Modelo de elevación: {dem_id}")
    imagen, bandas = construir_imagen(dem_id, args.tanda2)
    tiles, alto, ancho = armar_tiles(bbox)
    print(f"Región {args.region}: {ancho} x {alto} celdas en {len(tiles)} tiles")

    contador = [0]
    t0 = time.time()

    def trabajo(t):
        lon, lat, w, h, f, k = t
        ruta = cache / f"t_{f}_{k}.npy"
        if ruta.exists() and not args.rehacer:
            return
        arr = pedir(imagen, bandas, lon, lat, w, h, contador)
        tmp = ruta.with_suffix(".tmp.npy")
        np.save(tmp, arr)
        tmp.replace(ruta)

    with ThreadPoolExecutor(C.HILOS) as ex:
        for i, _ in enumerate(ex.map(trabajo, tiles), 1):
            if i % 10 == 0 or i == len(tiles):
                print(f"  {i}/{len(tiles)} tiles  ({time.time() - t0:.0f} s)")
    segundos = time.time() - t0

    # Un archivo por variable, con NaN donde no hay dato.
    print("\nResumen (celdas con dato):")
    for b, nombre_b in enumerate(bandas):
        mm = np.lib.format.open_memmap(salida / f"{nombre_b}.npy", mode="w+",
                                       dtype=np.float32, shape=(alto, ancho))
        for (_, _, w, h, f, k) in tiles:
            t = np.load(cache / f"t_{f}_{k}.npy")[b]
            mm[f:f + h, k:k + w] = np.where(t == C.NODATA, np.nan, t)
        ok = np.isfinite(mm)
        if ok.any():
            v = mm[ok]
            print(f"  {nombre_b:14s} min={v.min():9.3f}  media={v.mean():9.3f}  "
                  f"max={v.max():9.3f}  ({ok.mean() * 100:.0f}% de las celdas)")
        else:
            print(f"  {nombre_b:14s} SIN DATOS")
        vista_previa(mm, salida / f"vista_{nombre_b}.png")
        mm.flush()

    meta = {
        "region": args.region, "bbox": bbox, "celda_grados": C.CELDA_GRADOS,
        "forma": [alto, ancho], "bandas": bandas, "dem": dem_id,
        "albedo_anios": C.ALBEDO_ANIOS, "ndvi_fechas": [C.NDVI_DESDE, C.NDVI_HASTA],
        "pedidos": contador[0], "segundos": round(segundos, 1),
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (salida / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"\nGuardado en {salida}")
    print(f"Pedidos a Earth Engine en esta corrida: {contador[0]}, en {segundos:.0f} s")
    print("Para ver la cuota gastada: consola de Google Cloud del proyecto "
          f"{C.PROYECTO} > Earth Engine. Anotá el valor antes y después.")


if __name__ == "__main__":
    main()
