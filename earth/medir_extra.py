"""
Rol Tierra, segunda pasada: baja en un solo pedido por tile lo que le falta a
medir.py, sin volver a pedir lo que ya está en earth/datos/<region>/.

Para cada celda de 0.05° calcula:
  desvio_m       desvío estándar de la elevación (a ~463 m) dentro de la celda.
                 Es la definición de "roughness" de docs/contratos.md y de Marte;
                 reemplaza a relieve_m / RELIEVE_A_DESVIO.
  temp_dia_C     temperatura de superficie de día (MODIS MOD11A2), media del período
  temp_noche_C   temperatura de superficie de noche, media del período

Usa la misma grilla, los mismos tiles y el mismo cache reanudable que medir.py.
Escribe en earth/datos/<region>_extra/ y earth/cache/<region>_extra/.

Uso:
  python earth/medir_extra.py --region noa
  python earth/medir_extra.py --region mundo     (NO correr sin confirmar: gasta cuota)
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import ee
import numpy as np

import config as C
import medir as M

BANDAS = ["desvio_m", "temp_dia_C", "temp_noche_C"]


def construir_imagen(dem_id):
    d = C.CELDA_GRADOS / C.SUBCELDAS
    fino = [d, 0, -180, 0, -d, 90]            # la misma grilla de ~463 m que medir.py
    dem = (
        ee.ImageCollection(dem_id)
        .select(C.DEM_BANDA)
        .map(lambda i: i.resample("bilinear"))
        .mosaic()
        .reproject(crs="EPSG:4326", crsTransform=fino)
    )
    desvio = dem.reduceResolution(reducer=ee.Reducer.stdDev(),
                                  maxPixels=C.SUBCELDAS ** 2 + 112)

    lst = ee.ImageCollection("MODIS/061/MOD11A2").filterDate(C.TEMP_DESDE, C.TEMP_HASTA)

    def celsius(banda):
        return lst.select(banda).mean().multiply(0.02).subtract(273.15)

    capas = [
        desvio.rename("desvio_m"),
        celsius("LST_Day_1km").rename("temp_dia_C"),
        celsius("LST_Night_1km").rename("temp_noche_C"),
    ]
    return ee.Image.cat(capas).unmask(C.NODATA).toFloat()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="noa", choices=sorted(C.REGIONES))
    ap.add_argument("--rehacer", action="store_true", help="ignora el cache")
    args = ap.parse_args()

    ee.Initialize(project=C.PROYECTO)
    bbox = C.REGIONES[args.region]
    cache = M.AQUI / "cache" / f"{args.region}_extra"
    salida = M.AQUI / "datos" / f"{args.region}_extra"
    cache.mkdir(parents=True, exist_ok=True)
    salida.mkdir(parents=True, exist_ok=True)

    dem_id = M.elegir_dem()
    print(f"Modelo de elevación: {dem_id}")
    imagen = construir_imagen(dem_id)
    tiles, alto, ancho = M.armar_tiles(bbox)
    print(f"Región {args.region}: {ancho} x {alto} celdas en {len(tiles)} tiles")

    contador = [0]
    t0 = time.time()

    def trabajo(t):
        lon, lat, w, h, f, k = t
        ruta = cache / f"t_{f}_{k}.npy"
        if ruta.exists() and not args.rehacer:
            return
        arr = M.pedir(imagen, BANDAS, lon, lat, w, h, contador)
        tmp = ruta.with_suffix(".tmp.npy")
        np.save(tmp, arr)
        tmp.replace(ruta)

    with ThreadPoolExecutor(C.HILOS) as ex:
        for i, _ in enumerate(ex.map(trabajo, tiles), 1):
            if i % 10 == 0 or i == len(tiles):
                print(f"  {i}/{len(tiles)} tiles  ({time.time() - t0:.0f} s)")
    segundos = time.time() - t0

    print("\nResumen (celdas con dato):")
    for b, nombre in enumerate(BANDAS):
        mm = np.lib.format.open_memmap(salida / f"{nombre}.npy", mode="w+",
                                       dtype=np.float32, shape=(alto, ancho))
        for (_, _, w, h, f, k) in tiles:
            t = np.load(cache / f"t_{f}_{k}.npy")[b]
            mm[f:f + h, k:k + w] = np.where(t == C.NODATA, np.nan, t)
        ok = np.isfinite(mm)
        if ok.any():
            v = mm[ok]
            print(f"  {nombre:14s} min={v.min():9.3f}  media={v.mean():9.3f}  "
                  f"max={v.max():9.3f}  ({ok.mean() * 100:.0f}% de las celdas)")
        else:
            print(f"  {nombre:14s} SIN DATOS")
        M.vista_previa(mm, salida / f"vista_{nombre}.png")
        mm.flush()

    meta = {
        "region": args.region, "bbox": bbox, "celda_grados": C.CELDA_GRADOS,
        "forma": [alto, ancho], "bandas": BANDAS, "dem": dem_id,
        "temp_fechas": [C.TEMP_DESDE, C.TEMP_HASTA],
        "pedidos": contador[0], "segundos": round(segundos, 1),
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (salida / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"\nGuardado en {salida}")
    print(f"Pedidos a Earth Engine en esta corrida: {contador[0]}, en {segundos:.0f} s")


if __name__ == "__main__":
    main()
