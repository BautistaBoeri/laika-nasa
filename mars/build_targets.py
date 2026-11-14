#!/usr/bin/env python3
"""Mide las variables en los sitios objetivo de Marte y escribe mars/targets.json.

Uso (desde la raíz del repo):

    .venv/bin/python mars/build_targets.py

Baja los rasters a data/ si no están, los revisa, mide cada sitio de TARGETS y
calcula las estadísticas de todo Marte. El formato de salida está en
docs/contratos.md.

Cómo se mide (lo mismo que hace earth/ del otro lado):

- Píxel de trabajo de 463,09 m reales en las dos direcciones. MOLA está en
  proyección cilíndrica: el píxel mide 463 m de norte a sur, pero de este a
  oeste mide 463 m * cos(latitud). Antes de medir, cada franja se promedia de
  este a oeste hasta que el píxel vuelve a medir 463 m en su latitud.
- Pendiente: diferencias centrales sobre ese modelo, en grados.
- Celda de análisis: 11 x 11 píxeles (5,09 km de lado).
    slope     = promedio de la pendiente en la celda
    roughness = desvío estándar de la elevación en la celda
    albedo    = albedo TES en el centro de la celda (TES es más grueso que la celda)
- Valor de un sitio: media y desvío de las celdas cuyo centro cae dentro del
  círculo de radius_km.
"""

from __future__ import annotations

import json
import math
import sys
import urllib.request
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = Path(__file__).resolve().parent / "targets.json"

MOLA = (
    "Mars_MGS_MOLA_DEM_mosaic_global_463m.tif",
    "https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif",
)
TES = (
    "Mars_MGS_TES_Albedo_mosaic_global_7410m.tif",
    "https://planetarymaps.usgs.gov/mosaic/Mars_MGS_TES_Albedo_mosaic_global_7410m.tif",
)

# Sitios objetivo. Agregar un sitio es agregar una entrada.
# Jezero: punto de aterrizaje de Perseverance (Octavia E. Butler Landing),
# 18,4447° N 77,4508° E; coincide con el 18,44 / 77,45 del contrato.
TARGETS = [
    {"id": "jezero", "name": "Cráter Jezero", "lat": 18.44, "lon": 77.45, "radius_km": 25},
]

PIXEL_M = 463.0935  # píxel de MOLA en el ecuador; todo se mide con píxeles de este tamaño real
BLOCK = 11  # píxeles por lado de la celda de análisis (11 * 463 m = 5,09 km)
CELL_M = PIXEL_M * BLOCK
BAND_ROWS = 10 * BLOCK  # alto de cada franja para las estadísticas globales (~0,9° de latitud; cabe en poca RAM)
MAX_LAT = 87.0  # MOLA y TES no tienen cobertura real más cerca de los polos
TES_NODATA_MAX = 0.0601  # el raster de TES rellena con 0,06 donde no hay dato


# ---------------------------------------------------------------- descarga


def ensure_raster(name: str, url: str) -> Path:
    path = DATA / name
    if path.exists():
        return path
    DATA.mkdir(exist_ok=True)
    part = path.with_suffix(".part")
    print(f"Bajando {name} ...", flush=True)
    # el servidor de USGS rechaza con 403 el identificador por defecto de Python
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; mars-analog-search/1.0)"})
    with urllib.request.urlopen(request) as resp, open(part, "wb") as f:
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        step = 0
        while chunk := resp.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if done // (200 << 20) > step:
                step = done // (200 << 20)
                print(f"  {done / 1e9:.1f} de {total / 1e9:.1f} GB", flush=True)
    part.rename(path)
    return path


def check_rasters(mola: rasterio.DatasetReader, tes: rasterio.DatasetReader) -> None:
    """Revisa lo que el resto del código da por cierto y lo imprime."""
    print("MOLA:", mola.width, "x", mola.height, mola.dtypes[0], "| píxel", round(mola.transform.a, 4), "m",
          "| sin dato", mola.nodata, "| escala", mola.scales[0], "| offset", mola.offsets[0])
    print("     ", mola.crs.to_wkt()[:60], "...")
    print("TES: ", tes.width, "x", tes.height, tes.dtypes[0], "| píxel", round(tes.transform.a, 1), "m",
          "| sin dato", tes.nodata)
    assert "Equirectangular" in mola.crs.to_wkt() and "Equirectangular" in tes.crs.to_wkt(), "proyección inesperada"
    assert abs(mola.transform.a - PIXEL_M) < 0.01 and abs(mola.transform.e + PIXEL_M) < 0.01, "píxel de MOLA inesperado"
    assert mola.dtypes[0] == "int16" and mola.scales[0] == 1.0 and mola.offsets[0] == 0.0, "MOLA trae factor de escala"
    assert mola.width == 2 * mola.height and tes.width == 2 * tes.height, "los rasters no son globales"


# ---------------------------------------------------------------- geometría


def resample_ew(strip: np.ndarray, cos_ref: float) -> np.ndarray:
    """Promedia una franja de MOLA de este a oeste hasta píxeles de PIXEL_M reales.

    En la franja, cada píxel nativo mide PIXEL_M * cos(lat) de ancho. El píxel
    nuevo abarca 1 / cos_ref píxeles nativos, ponderados por la parte que cubre
    de cada uno. De norte a sur no se toca nada.
    """
    rows, n_src = strip.shape
    n_dst = int(n_src * cos_ref)
    edges = np.arange(n_dst + 1) / cos_ref  # bordes de los píxeles nuevos, en píxeles nativos
    i = np.minimum(edges.astype(np.int64), n_src - 1)
    frac = edges - i
    csum = np.zeros((rows, n_src + 1), dtype=np.float64)
    np.cumsum(strip, axis=1, dtype=np.float64, out=csum[:, 1:])
    at_edges = csum[:, i] + frac * strip[:, i]
    return (np.diff(at_edges, axis=1) * cos_ref).astype(np.float32)


def slope_deg(dem: np.ndarray, dx: np.ndarray | float, dy: float = PIXEL_M) -> np.ndarray:
    """Pendiente en grados por diferencias centrales. dx y dy son el tamaño real del píxel en metros."""
    gy, gx = np.gradient(dem)
    return np.degrees(np.arctan(np.hypot(gx / dx, gy / dy)))


def by_block(a: np.ndarray, func) -> np.ndarray:
    """Aplica func a cada celda de BLOCK x BLOCK píxeles."""
    ny, nx = a.shape[0] // BLOCK, a.shape[1] // BLOCK
    v = a[: ny * BLOCK, : nx * BLOCK].reshape(ny, BLOCK, nx, BLOCK).swapaxes(1, 2).reshape(ny, nx, BLOCK * BLOCK)
    return func(v, axis=2)


def row_lat(mola: rasterio.DatasetReader, row: np.ndarray | float) -> np.ndarray | float:
    """Latitud del centro de una fila de MOLA."""
    return 90.0 - (np.asarray(row) + 0.5) * 180.0 / mola.height


# ---------------------------------------------------------------- variables
#
# Cada variable recibe un parche ya llevado a píxeles cuadrados de 463 m y
# devuelve un valor por celda. Agregar una variable es agregar una entrada.


def var_slope(p: dict) -> np.ndarray:
    return by_block(p["slope"], np.mean)


def var_roughness(p: dict) -> np.ndarray:
    return by_block(p["dem"], np.std)


def var_albedo(p: dict) -> np.ndarray:
    tes = p["tes"]
    r = np.clip(((90.0 - p["cell_lat"]) * tes.shape[0] / 180.0).astype(int), 0, tes.shape[0] - 1)
    c = ((p["cell_lon"] + 180.0) * tes.shape[1] / 360.0).astype(int) % tes.shape[1]
    a = tes[r[:, None], c[None, :]].astype(np.float64)
    a[a <= TES_NODATA_MAX] = np.nan
    return a


VARIABLES = {
    "slope": var_slope,
    "roughness": var_roughness,
    "albedo": var_albedo,
}
DECIMALS = {"slope": 3, "roughness": 2, "albedo": 4}


def make_patch(mola, tes, r0: int, r1: int, c0: int, c1: int, lat_ref: float) -> dict:
    """Lee filas [r0, r1) y columnas [c0, c1) de MOLA con un píxel de margen para el
    gradiente, las lleva a píxeles cuadrados y arma lo que usan las variables."""
    cos_ref = math.cos(math.radians(lat_ref))
    ra, rb = max(r0 - 1, 0), min(r1 + 1, mola.height)
    strip = mola.read(1, window=Window(c0, ra, c1 - c0, rb - ra)).astype(np.float32)
    assert not (strip == mola.nodata).any(), "MOLA tiene píxeles sin dato en la zona"
    dem = resample_ew(strip, cos_ref)
    lat_rows = row_lat(mola, np.arange(ra, rb))
    dx = (PIXEL_M * np.cos(np.radians(lat_rows)) / cos_ref)[:, None].astype(np.float32)
    slope = slope_deg(dem, dx)
    top = r0 - ra
    dem, slope, lat_rows = dem[top : top + r1 - r0], slope[top : top + r1 - r0], lat_rows[top : top + r1 - r0]
    ny, nx = dem.shape[0] // BLOCK, dem.shape[1] // BLOCK
    cell_lat = lat_rows[: ny * BLOCK].reshape(ny, BLOCK).mean(axis=1)
    # columna nueva j -> columna nativa (j + 0.5) / cos_ref -> longitud
    native_col = c0 + (np.arange(nx) * BLOCK + BLOCK / 2) / cos_ref
    cell_lon = -180.0 + native_col * 360.0 / mola.width
    return {"dem": dem, "slope": slope, "tes": tes, "cell_lat": cell_lat, "cell_lon": cell_lon}


# ---------------------------------------------------------------- medición


def measure_target(mola, tes, t: dict) -> dict:
    lat, lon, radius_m = t["lat"], t["lon"], t["radius_km"] * 1000.0
    cos_ref = math.cos(math.radians(lat))
    nb = math.ceil(radius_m / CELL_M) + 1  # celdas a cada lado de la celda central
    half = nb * BLOCK + BLOCK // 2
    row_c = int((90.0 - lat) * mola.height / 180.0)
    col_c = int((lon + 180.0) * mola.width / 360.0)
    half_native = math.ceil((half + 2) / cos_ref) + 2
    c0 = col_c - half_native
    p = make_patch(mola, tes, row_c - half, row_c + half + 1, c0, col_c + half_native + 1, lat)
    # recortar de este a oeste para que la celda central quede sobre el sitio
    j_c = int((col_c + 0.5 - c0) * cos_ref)
    j0 = j_c - half
    assert j0 >= 0 and j_c + half + 1 <= p["dem"].shape[1]
    p["dem"] = p["dem"][:, j0 : j_c + half + 1]
    p["slope"] = p["slope"][:, j0 : j_c + half + 1]
    n = 2 * nb + 1
    native_col = c0 + (j0 + np.arange(n) * BLOCK + BLOCK / 2) / cos_ref
    p["cell_lon"] = -180.0 + native_col * 360.0 / mola.width

    # distancia de cada centro de celda al sitio, en metros
    k = np.arange(n) - nb
    dist = np.hypot(k[:, None] * CELL_M, k[None, :] * CELL_M)
    inside = dist <= radius_m
    values = {}
    for vid, func in VARIABLES.items():
        v = func(p)[inside]
        v = v[~np.isnan(v)]
        values[vid] = {"mean": round(float(v.mean()), DECIMALS[vid]), "std": round(float(v.std()), DECIMALS[vid])}
    print(f"{t['id']}: {int(inside.sum())} celdas en el círculo de {t['radius_km']} km "
          f"(cota media {p['dem'].mean():.0f} m) -> {values}")
    return {**t, "values": values}


def measure_global(mola, tes) -> dict:
    """Media y desvío de cada variable sobre todas las celdas de Marte, ponderadas por área."""
    acc = {vid: np.zeros(3) for vid in VARIABLES}  # suma de pesos, de w*v y de w*v^2
    row_top = int((90.0 - MAX_LAT) * mola.height / 180.0)
    row_bot = mola.height - row_top
    starts = range(row_top, row_bot, BAND_ROWS)
    for n, r0 in enumerate(starts):
        r1 = min(r0 + BAND_ROWS, row_bot)
        r1 = r0 + (r1 - r0) // BLOCK * BLOCK
        if r1 == r0:
            continue
        lat_ref = float(row_lat(mola, (r0 + r1 - 1) / 2))
        p = make_patch(mola, tes, r0, r1, 0, mola.width, lat_ref)
        w_row = np.cos(np.radians(p["cell_lat"])) / math.cos(math.radians(lat_ref))
        for vid, func in VARIABLES.items():
            v = func(p)
            w = np.broadcast_to(w_row[:, None], v.shape)
            ok = ~np.isnan(v)
            acc[vid] += [w[ok].sum(), (w[ok] * v[ok]).sum(), (w[ok] * v[ok] ** 2).sum()]
        if n % 25 == 0:
            print(f"  global: franja {n + 1} de {len(starts)} (lat {lat_ref:+.1f})", flush=True)
    out = {}
    for vid, (sw, swv, swv2) in acc.items():
        mean = swv / sw
        out[vid] = {"mean": round(mean, DECIMALS[vid]), "std": round(math.sqrt(swv2 / sw - mean**2), DECIMALS[vid])}
    return out


def main() -> None:
    mola_path, tes_path = ensure_raster(*MOLA), ensure_raster(*TES)
    with rasterio.open(mola_path) as mola, rasterio.open(tes_path) as tes_ds:
        check_rasters(mola, tes_ds)
        tes = tes_ds.read(1)
        sat = float((tes >= 0.3199).mean())
        print(f"TES: {100 * float((tes <= TES_NODATA_MAX).mean()):.1f} % sin dato (polos), "
              f"{100 * sat:.1f} % saturado en 0,32 (casquetes)")
        targets = [measure_target(mola, tes, t) for t in TARGETS]
        print("Estadísticas de todo Marte ...", flush=True)
        mars_global = measure_global(mola, tes)
    print("mars_global:", mars_global)
    OUT.write_text(json.dumps({"targets": targets, "mars_global": mars_global}, indent=2, ensure_ascii=False) + "\n")
    print("Escrito", OUT.relative_to(ROOT))


if __name__ == "__main__":
    sys.exit(main())
