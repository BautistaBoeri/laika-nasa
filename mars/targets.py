"""Calcula mars/targets.json a partir de los rasters globales de Marte.

Variables (definidas en docs/contratos.md):
  slope      pendiente media (grados) dentro de una celda de ~5 km, sobre MOLA de 463 m
  roughness  desvío estándar de la elevación (m) dentro de una celda de ~5 km
  albedo     albedo bolométrico TES (fracción 0-1)
  thermal    percentil (0-1) de la inercia térmica nocturna TES dentro de todo Marte,
             ponderado por área. El diseño compara lo térmico por percentil en cada planeta.
  thermal_inertia  la misma inercia térmica en su unidad (J m-2 K-1 s-1/2), como referencia
  dust       percentil (0-1) de cobertura de polvo dentro de todo Marte, ponderado por área;
             1 = lo más polvoriento. Se calcula sobre el índice de polvo TES invertido
             (en el índice original, menor emisividad = más polvo).
  dust_cover_index el índice original (emisividad media 1350-1400 cm-1), como referencia

Valor de un sitio: media y desvío de los valores de las celdas cuyo centro cae
dentro de un círculo de `radius_km` alrededor del punto.
`mars_global`: media y desvío de todas las celdas de Marte entre ±LAT_MAX.

Rasters esperados en /data/ (raíz del repo, no va a git):
  Mars_MGS_MOLA_DEM_mosaic_global_463m.tif
  Mars_MGS_TES_Albedo_mosaic_global_7410m.tif
  NBmap2007.bin, NBmsk2007.bin  (inercia térmica nocturna, Putzig y Mellon 2007,
                                 https://se.psi.edu/inertia/2007/)
  dci_lo_ice_dust_16ppd_shifted.pds  (índice de polvo TES, Ruff y Christensen 2002,
                                      http://tes.asu.edu/~ruff/DCI/dci.html)

Uso:
  python mars/targets.py            # sitios + estadísticas globales
  python mars/targets.py --no-global  # solo sitios (rápido)
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MOLA = DATA / "Mars_MGS_MOLA_DEM_mosaic_global_463m.tif"
ALBEDO = DATA / "Mars_MGS_TES_Albedo_mosaic_global_7410m.tif"
TI_MAP = DATA / "NBmap2007.bin"
TI_MASK = DATA / "NBmsk2007.bin"
DCI = DATA / "dci_lo_ice_dust_16ppd_shifted.pds"
OUT = Path(__file__).resolve().parent / "targets.json"

R_MARS = 3_396_190.0  # radio de referencia de Marte (m)
CELL_KM = 5.0         # tamaño de la celda de comparación
LAT_MAX = 85.0        # cerca de los polos las celdas degeneran; se excluyen

# Coordenadas: lat planetocéntrica, lon en grados este de -180 a 180.
TARGETS = [
    {"id": "jezero", "name": "Cráter Jezero", "lat": 18.4447, "lon": 77.4508, "radius_km": 25},
    {"id": "gale", "name": "Cráter Gale", "lat": -4.5895, "lon": 137.4417, "radius_km": 25},
    {"id": "arcadia", "name": "Arcadia Planitia", "lat": 47.0, "lon": -176.0, "radius_km": 25},
]


def read_elevation(src, window):
    """Lee una ventana de elevación en metros, con NaN donde no hay dato."""
    z = src.read(1, window=window).astype(np.float64)
    if src.nodata is not None:
        z[z == src.nodata] = np.nan
    return z * src.scales[0] + src.offsets[0]


def row_lat(src, rows):
    """Latitud (grados) del centro de cada fila."""
    return 90.0 - (np.asarray(rows) + 0.5) * 180.0 / src.height


def col_lon(src, cols):
    return -180.0 + (np.asarray(cols) + 0.5) * 360.0 / src.width


def slope_deg(z, lats, src):
    """Pendiente en grados, con el ancho este-oeste del píxel corregido por cos(lat)."""
    dy = math.pi * R_MARS / src.height             # alto del píxel (m), constante
    dx0 = 2 * math.pi * R_MARS / src.width         # ancho del píxel en el ecuador (m)
    dz_dy = np.gradient(z, axis=0) / dy
    dz_dx = np.gradient(z, axis=1) / (dx0 * np.cos(np.radians(lats)))[:, None]
    return np.degrees(np.arctan(np.hypot(dz_dx, dz_dy)))


def cells(z, s, lat_center, src):
    """Agrupa una franja en celdas de ~5 km y devuelve (slope, roughness, col_centro)."""
    dx_km = 2 * math.pi * R_MARS / src.width / 1000 * math.cos(math.radians(lat_center))
    nc = max(1, round(CELL_KM / dx_km))            # columnas por celda (crece con la latitud)
    nr = z.shape[0]
    ncell = z.shape[1] // nc
    zc = z[:, : ncell * nc].reshape(nr, ncell, nc)
    sc = s[:, : ncell * nc].reshape(nr, ncell, nc)
    with np.errstate(invalid="ignore"):
        slope = np.nanmean(sc, axis=(0, 2))
        rough = np.nanstd(zc, axis=(0, 2))
    centers = np.arange(ncell) * nc + nc / 2
    return slope, rough, centers


def rows_per_cell(src):
    return max(1, round(CELL_KM * 1000 / (math.pi * R_MARS / src.height)))


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dl = np.radians(lon2 - lon1)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R_MARS / 1000 * np.arcsin(np.sqrt(a))


def stats(values):
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    return {"mean": round(float(v.mean()), 4), "std": round(float(v.std()), 4), "n": int(v.size)}


def site_topography(src, t):
    """Pendiente y relieve de las celdas de 5 km dentro del círculo del sitio."""
    nr = rows_per_cell(src)
    km_per_row = math.pi * R_MARS / src.height / 1000
    half_rows = int(t["radius_km"] / km_per_row) + 2 * nr
    row0 = int((90.0 - t["lat"]) / 180.0 * src.height)
    # Alinear las celdas con la grilla global (múltiplos de nr), igual que en el cálculo global
    r_start = ((row0 - half_rows) // nr) * nr
    r_end = ((row0 + half_rows) // nr + 1) * nr

    slopes, roughs = [], []
    for r in range(r_start, r_end, nr):
        lat_c = float(row_lat(src, r + nr / 2 - 0.5))
        dx_km = 2 * math.pi * R_MARS / src.width / 1000 * math.cos(math.radians(lat_c))
        nc = max(1, round(CELL_KM / dx_km))
        half_cols = int(t["radius_km"] / dx_km) + 2 * nc
        col0 = int((t["lon"] + 180.0) / 360.0 * src.width)
        c_start = ((col0 - half_cols) // nc) * nc
        c_end = ((col0 + half_cols) // nc + 1) * nc
        # Leer con un píxel de margen para el gradiente
        win = Window(c_start - 1, r - 1, c_end - c_start + 2, nr + 2)
        z = read_elevation(src, win)
        lats = row_lat(src, np.arange(r - 1, r + nr + 1))
        s = slope_deg(z, lats, src)[1:-1, 1:-1]
        z = z[1:-1, 1:-1]
        sl, ro, centers = cells(z, s, lat_c, src)
        lon_c = col_lon(src, c_start + centers - 0.5)
        inside = haversine_km(t["lat"], t["lon"], lat_c, lon_c) <= t["radius_km"]
        slopes.extend(sl[inside])
        roughs.extend(ro[inside])
    return stats(slopes), stats(roughs)


def site_albedo(src, t):
    a = src.read(1).astype(np.float64)
    if src.nodata is not None:
        a[a == src.nodata] = np.nan
    lats = row_lat(src, np.arange(src.height))[:, None]
    lons = col_lon(src, np.arange(src.width))[None, :]
    inside = haversine_km(t["lat"], t["lon"], lats, lons) <= t["radius_km"]
    vals = a[inside]
    if not np.isfinite(vals).any():  # el círculo es más chico que un píxel: tomar el más cercano
        d = haversine_km(t["lat"], t["lon"], lats, lons)
        vals = a[np.unravel_index(np.argmin(d), d.shape)][None]
    return stats(vals)


def global_topography(src):
    """Estadísticas de pendiente y relieve de todas las celdas de 5 km entre ±LAT_MAX."""
    nr = rows_per_cell(src)
    slopes, roughs = [], []
    n_bands = src.height // nr
    for b in range(n_bands):
        r = b * nr
        lat_c = float(row_lat(src, r + nr / 2 - 0.5))
        if abs(lat_c) > LAT_MAX:
            continue
        r0, r1 = max(r - 1, 0), min(r + nr + 1, src.height)
        z = read_elevation(src, Window(0, r0, src.width, r1 - r0))
        lats = row_lat(src, np.arange(r0, r1))
        s = slope_deg(z, lats, src)
        top = r - r0
        z, s = z[top : top + nr], s[top : top + nr]
        sl, ro, _ = cells(z, s, lat_c, src)
        slopes.append(sl.astype(np.float32))
        roughs.append(ro.astype(np.float32))
        if b % 200 == 0:
            print(f"  franja {b}/{n_bands} (lat {lat_c:.1f})", flush=True)
    return stats(np.concatenate(slopes)), stats(np.concatenate(roughs))


def global_albedo(src):
    """Media y desvío del albedo ponderados por área (cos lat), entre ±LAT_MAX."""
    a = src.read(1).astype(np.float64)
    if src.nodata is not None:
        a[a == src.nodata] = np.nan
    lats = row_lat(src, np.arange(src.height))
    w = np.broadcast_to(np.cos(np.radians(lats))[:, None], a.shape).copy()
    ok = np.isfinite(a) & (np.abs(lats)[:, None] <= LAT_MAX)
    mean = np.average(a[ok], weights=w[ok])
    std = math.sqrt(np.average((a[ok] - mean) ** 2, weights=w[ok]))
    return {"mean": round(float(mean), 4), "std": round(float(std), 4), "n": int(ok.sum())}


def load_thermal_inertia():
    """Lee el mapa de Putzig y lo deja con fila 0 = 90°N y columnas de -180 a 180 °E.

    Formato del archivo (encabezado): 7200 x 3600 enteros de 2 bytes big-endian,
    0,05° por píxel, longitudes 0-360 °W, primera fila = polo sur, 0 = sin dato.
    La orientación se verificó contra el albedo TES (correlación -0,69).
    La máscara vale 1 donde hay observación y 0 donde se rellenó por interpolación;
    se descartan los píxeles interpolados.
    """
    ti = np.fromfile(TI_MAP, dtype=">i2", offset=14400).reshape(3600, 7200).astype(np.float64)
    mask = np.fromfile(TI_MASK, dtype=np.uint8, offset=7200).reshape(3600, 7200)
    ti[(ti == 0) | (mask == 0)] = np.nan
    ti = ti[::-1]                                        # fila 0 = norte
    east = -180 + (np.arange(7200) + 0.5) * 0.05         # centro de cada columna en °E
    cols = np.floor(((-east) % 360) / 0.05).astype(int)  # columna equivalente en °W
    return ti[:, cols]


def load_dust_cover_index():
    """Lee el índice de polvo TES con fila 0 = 90°N y columnas de -180 a 180 °E.

    Formato (etiqueta PDS): 5760 x 2880 float32 little-endian, 16 píxeles por grado,
    datos desde el byte 1024. La etiqueta no trae georreferencia; la orientación se
    verificó contra el albedo TES (correlación -0,73). El valor 0,85 es relleno
    (aparece casi solo al norte de 60°N y al sur de 60°S) y se trata como sin dato.
    """
    d = np.fromfile(DCI, dtype="<f4", offset=1024, count=5760 * 2880).reshape(2880, 5760)
    d = d.astype(np.float64)
    d[np.isclose(d, 0.85, atol=1e-6) | ~np.isfinite(d)] = np.nan
    return d


class Percentile:
    """Percentil ponderado por área (cos lat) de un valor dentro de la distribución de Marte."""

    def __init__(self, grid):
        lats = 90 - (np.arange(grid.shape[0]) + 0.5) * 180 / grid.shape[0]
        w = np.broadcast_to(np.cos(np.radians(lats))[:, None], grid.shape)
        ok = np.isfinite(grid) & (np.abs(lats)[:, None] <= LAT_MAX)
        order = np.argsort(grid[ok])
        self.values = grid[ok][order]
        cw = np.cumsum(w[ok][order])
        self.cdf = cw / cw[-1]
        self.lats, self.weights, self.ok = lats, w, ok

    def __call__(self, v):
        idx = np.searchsorted(self.values, v, side="right") - 1
        return np.where(idx >= 0, self.cdf[np.clip(idx, 0, None)], 0.0)


def site_grid(grid, pct, t, sign=1):
    """Percentil y valor original de una grilla global (fila 0 = norte, -180 a 180 °E)
    en el círculo del sitio. `sign=-1` cuando el percentil se calcula sobre -grid."""
    res = 180 / grid.shape[0]
    lats = 90 - (np.arange(grid.shape[0]) + 0.5) * res
    lons = -180 + (np.arange(grid.shape[1]) + 0.5) * res
    r = np.abs(lats - t["lat"]) <= t["radius_km"] / (math.pi * R_MARS / 180_000) + 0.1
    sub = grid[r]
    inside = haversine_km(t["lat"], t["lon"], lats[r][:, None], lons[None, :]) <= t["radius_km"]
    vals = sub[inside]
    vals = vals[np.isfinite(vals)]
    return stats(pct(sign * vals)), stats(vals)


def global_grid(grid, pct, sign=1):
    """Media y desvío ponderados por área: del percentil (≈0,5 y ≈0,29) y del valor original."""
    w = pct.weights[pct.ok]
    raw = grid[pct.ok]
    out = []
    for v in (pct(sign * raw), raw):
        mean = np.average(v, weights=w)
        std = math.sqrt(np.average((v - mean) ** 2, weights=w))
        out.append({"mean": round(float(mean), 4), "std": round(float(std), 4), "n": int(v.size)})
    return out


def strip_n(d):
    """El contrato no lleva `n`; se imprime para control y se saca del JSON."""
    return {"mean": d["mean"], "std": d["std"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-global", action="store_true", help="no recalcular mars_global")
    args = ap.parse_args()

    out = {"targets": [], "mars_global": {}}
    if args.no_global and OUT.exists():
        out["mars_global"] = json.loads(OUT.read_text()).get("mars_global", {})

    ti = load_thermal_inertia()
    pct_ti = Percentile(ti)
    dci = load_dust_cover_index()
    pct_dust = Percentile(-dci)  # invertido: más polvo = percentil más alto

    with rasterio.open(MOLA) as mola, rasterio.open(ALBEDO) as alb:
        for t in TARGETS:
            sl, ro = site_topography(mola, t)
            al = site_albedo(alb, t)
            th, tir = site_grid(ti, pct_ti, t)
            du, dcir = site_grid(dci, pct_dust, t, sign=-1)
            print(f"{t['id']}: slope={sl} roughness={ro} albedo={al}\n"
                  f"   thermal={th} TI={tir}\n   dust={du} DCI={dcir}")
            out["targets"].append({**t, "values": {
                "slope": strip_n(sl), "roughness": strip_n(ro), "albedo": strip_n(al),
                "thermal": strip_n(th), "thermal_inertia": strip_n(tir),
                "dust": strip_n(du), "dust_cover_index": strip_n(dcir)}})

        th, tir = global_grid(ti, pct_ti)
        du, dcir = global_grid(dci, pct_dust, sign=-1)
        print(f"global: thermal={th} TI={tir}\n   dust={du} DCI={dcir}")
        if not args.no_global:
            print("Estadísticas globales (recorre todo MOLA, tarda unos minutos)...")
            sl, ro = global_topography(mola)
            al = global_albedo(alb)
            print(f"global: slope={sl} roughness={ro} albedo={al}")
            out["mars_global"] = {"slope": strip_n(sl), "roughness": strip_n(ro), "albedo": strip_n(al)}
        out["mars_global"]["thermal"] = strip_n(th)
        out["mars_global"]["thermal_inertia"] = strip_n(tir)
        out["mars_global"]["dust"] = strip_n(du)
        out["mars_global"]["dust_cover_index"] = strip_n(dcir)

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print(f"Escrito {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
