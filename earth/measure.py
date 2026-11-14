"""Mide las variables de la Tierra en Earth Engine, sobre la misma grilla que Marte.

La grilla
---------
Marte se mide con píxeles de 463,09 m reales y celdas de 11 x 11 píxeles
(5,09 km). Acá se hace lo mismo: el modelo de elevación se promedia a 463,09 m
ANTES de calcular la pendiente y el relieve.

Un píxel de tamaño fijo en grados no mide lo mismo en metros a distintas
latitudes (de este a oeste se achica con el coseno). Por eso el planeta se
parte en franjas de latitud de ~1,8°, y cada franja tiene su propio ancho de
píxel en grados, elegido para que mida 463 m en el centro de la franja. Dentro
de la franja, la diferencia que queda se corrige al calcular la pendiente.

Earth Engine no deja bajar un raster global de 5 km de una vez: cada franja se
baja en pedazos de 64 celdas de ancho, que quedan guardados en
data/earth_cache/ para no volver a gastar cuota.

Las bandas están en grupos (GROUPS). Cada grupo se pide y se guarda por
separado, así que agregar un grupo nuevo no obliga a volver a bajar los demás.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import ee
import numpy as np

PROJECT = "laika-nasa"
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "earth_cache"

# --- grilla (tiene que coincidir con mars/build_targets.py)
PIXEL_M = 463.0935  # píxel de MOLA
BLOCK = 11  # celda de análisis = 11 x 11 píxeles
M_PER_DEG = 111195.08  # metros por grado de latitud (esfera de 6 371 008,8 m de radio)
PIX_DEG = PIXEL_M / M_PER_DEG
CELL_DEG = PIX_DEG * BLOCK
CELL_KM = PIXEL_M * BLOCK / 1000.0
BAND_ROWS = 40  # celdas de alto por franja
CHUNK_COLS = 64  # celdas de ancho por pedido a Earth Engine
LAT_MAX = 84.0
GRID = {"pixel_m": PIXEL_M, "block": BLOCK, "band_rows": BAND_ROWS, "chunk_cols": CHUNK_COLS, "lat_max": LAT_MAX}

# --- datos
DEM_ID = "COPERNICUS/DEM/GLO30_2024_1"  # reemplaza a COPERNICUS/DEM/GLO30, marcado como obsoleto
DEM_LEVEL = 4  # el DEM se lee en su nivel de 4 segundos de arco (~123 m): promedios exactos de 4 x 4 píxeles de 30 m
ALBEDO_ID, ALBEDO_BAND = "MODIS/061/MCD43A3", "Albedo_WSA_shortwave"
SNOW_ID, SNOW_BAND = "MODIS/061/MCD43A2", "Snow_BRDF_Albedo"
ALBEDO_LEVEL = 4  # el albedo se lee a 4 x 463 m = 1,85 km (promedios de 4 x 4 píxeles)
ALBEDO_STEP_DAYS = 16  # el albedo diario sale de una ventana móvil de 16 días
NDVI_ID = "MODIS/061/MOD13A2"
NDVI_LEVEL = 2  # el NDVI se lee a 2 x 927 m = 1,85 km
LC_ID, LC_BAND = "MODIS/061/MCD12Q1/2024_01_01", "LC_Type1"  # la de 2025 figura en el catálogo pero viene vacía
EXCLUDED_LC = [13, 15, 17]  # urbano, nieve o hielo permanente, agua
DATE_START, DATE_END = "2023-01-01", "2026-01-01"  # tres años completos

NODATA = -9999.0


# ---------------------------------------------------------------- grilla


@dataclass(frozen=True)
class Band:
    """Una franja de latitud con su propio ancho de celda en grados."""

    k: int
    top: float  # latitud del borde norte

    @property
    def lat_c(self) -> float:
        return self.top - BAND_ROWS * CELL_DEG / 2

    @property
    def dx(self) -> float:
        """Ancho de la celda en grados de longitud (5,09 km en el centro de la franja)."""
        return CELL_DEG / math.cos(math.radians(self.lat_c))

    @property
    def ncols(self) -> int:
        return math.ceil(360.0 / self.dx)

    def lats(self) -> np.ndarray:
        return self.top - (np.arange(BAND_ROWS) + 0.5) * CELL_DEG

    def lons(self, c0: int, n: int) -> np.ndarray:
        return -180.0 + (c0 + np.arange(n) + 0.5) * self.dx

    def chunks(self) -> list[tuple[int, int]]:
        """(columna inicial, cantidad de columnas) de cada pedido."""
        return [(c0, min(CHUNK_COLS, self.ncols - c0)) for c0 in range(0, self.ncols, CHUNK_COLS)]

    def bbox(self, c0: int, n: int) -> tuple[float, float, float, float]:
        """(oeste, sur, este, norte) de un pedazo."""
        return (-180.0 + c0 * self.dx, self.top - BAND_ROWS * CELL_DEG, -180.0 + (c0 + n) * self.dx, self.top)


def bands() -> list[Band]:
    n = math.ceil(2 * LAT_MAX / (BAND_ROWS * CELL_DEG))
    return [Band(k, LAT_MAX - k * BAND_ROWS * CELL_DEG) for k in range(n)]


# ---------------------------------------------------------------- imágenes de Earth Engine


def init() -> None:
    ee.Initialize(project=PROJECT)


def _dem_lon_step(lat: float) -> float:
    """Paso de longitud de las teselas de Copernicus GLO-30, en segundos de arco.
    Crece hacia los polos para que el píxel no se angoste (verificado en el catálogo)."""
    a = abs(lat)
    return 1.0 if a < 50 else 1.5 if a < 60 else 2.0 if a < 70 else 3.0 if a < 80 else 5.0 if a < 85 else 10.0


def dem_463(band: Band) -> tuple[ee.Image, ee.Projection]:
    """El modelo de elevación promediado a píxeles de 463 m reales, y su proyección.

    Promediar desde los 30 m nativos gasta unas 150 horas de cuota a escala
    global. En cambio se lee el nivel 2 de la pirámide del mismo DEM (4" de
    latitud, ~123 m), que son promedios exactos de 4 x 4 píxeles nativos
    (verificado), y se promedia de ahí a 463 m ponderando cada píxel por la
    parte que cae adentro. En una prueba en la Puna la pendiente cambió 0,4 % y
    el relieve 0,2 %. La grilla de lectura sigue el paso de longitud nativo de
    cada latitud; si no, cerca de los polos se piden hasta 8 veces más píxeles.
    """
    a = 1 / 3600
    lon_step = _dem_lon_step(band.lat_c)
    level = ee.Projection("EPSG:4326", [DEM_LEVEL * lon_step * a, 0, -180 - lon_step * a / 2, 0, -DEM_LEVEL * a, 90 + a / 2])
    fine = ee.Projection("EPSG:4326", [band.dx / BLOCK, 0, -180, 0, -PIX_DEG, band.top])
    dem = ee.ImageCollection(DEM_ID).select("DEM").mosaic().unmask(0).setDefaultProjection(level)
    return dem.reduceResolution(ee.Reducer.mean(), maxPixels=1024).reproject(fine), fine


def _terrain(band: Band) -> dict[str, ee.Image]:
    dem, fine = dem_463(band)
    # Pendiente por diferencias centrales, igual que en Marte. El píxel mide
    # 463 m de norte a sur; de este a oeste, 463 m * cos(lat) / cos(lat del centro).
    lat = ee.Image.pixelLonLat().select("latitude")
    px_x = lat.multiply(math.pi / 180).cos().multiply(PIXEL_M / math.cos(math.radians(band.lat_c)))
    gx = dem.convolve(ee.Kernel.fixed(3, 3, [[0, 0, 0], [-0.5, 0, 0.5], [0, 0, 0]])).divide(px_x)
    gy = dem.convolve(ee.Kernel.fixed(3, 3, [[0, -0.5, 0], [0, 0, 0], [0, 0.5, 0]])).divide(PIXEL_M)
    slope = gx.hypot(gy).atan().multiply(180 / math.pi).reproject(fine)
    n = BLOCK * BLOCK + 7
    return {
        "slope": slope.reduceResolution(ee.Reducer.mean(), maxPixels=n),
        "roughness": dem.reduceResolution(ee.Reducer.stdDev(), maxPixels=n),
    }


def _albedo() -> ee.Image:
    """Albedo de onda corta sin nieve: promedio de 2023 a 2025, una fecha cada 16 días."""
    day, end = dt.date.fromisoformat(DATE_START), dt.date.fromisoformat(DATE_END)
    ids = []
    while day < end:
        ids.append(day.strftime("%Y_%m_%d"))
        day += dt.timedelta(days=ALBEDO_STEP_DAYS)
    chosen = ee.Filter.inList("system:index", ids)
    a3 = ee.ImageCollection(ALBEDO_ID).filter(chosen).select(ALBEDO_BAND)
    a2 = ee.ImageCollection(SNOW_ID).filter(chosen).select(SNOW_BAND)
    snow_free = a3.combine(a2).map(lambda i: i.select(ALBEDO_BAND).updateMask(i.select(SNOW_BAND).eq(0)))
    proj = a3.first().projection().scale(ALBEDO_LEVEL, ALBEDO_LEVEL)
    return snow_free.mean().multiply(0.001).setDefaultProjection(proj)


def _ndvi_mean() -> ee.Image:
    """NDVI medio de las observaciones buenas (sin nubes ni nieve), de 2023 a 2025."""
    c = ee.ImageCollection(NDVI_ID).filterDate(DATE_START, DATE_END)
    return c.map(lambda i: i.select("NDVI").updateMask(i.select("SummaryQA").lte(1))).mean().multiply(0.0001)


def _land() -> ee.Image:
    """1 donde hay tierra firme que sirve (ni agua, ni hielo permanente, ni ciudad), 0 si no."""
    return ee.Image(LC_ID).select(LC_BAND).unmask(17).remap(EXCLUDED_LC, [0] * len(EXCLUDED_LC), 1)


def _surface(band: Band) -> dict[str, ee.Image]:
    ndvi_proj = ee.ImageCollection(NDVI_ID).first().select("NDVI").projection().scale(NDVI_LEVEL, NDVI_LEVEL)
    lc_proj = ee.Image(LC_ID).select(LC_BAND).projection()
    mean = ee.Reducer.mean()
    return {
        "albedo": _albedo().reduceResolution(mean, maxPixels=256),
        "ndvi": _ndvi_mean().setDefaultProjection(ndvi_proj).reduceResolution(mean, maxPixels=256),
        "landfrac": _land().setDefaultProjection(lc_proj).reduceResolution(mean, maxPixels=512),
    }


# Grupos de bandas. "params" es todo lo que define la medición del grupo: si
# cambia, el grupo se vuelve a bajar a una carpeta nueva del caché.
GROUPS = {
    "terrain": {
        "bands": ["slope", "roughness"],
        "image": _terrain,
        "params": {"dem": DEM_ID, "dem_level_arcsec": DEM_LEVEL, "dem_lon_step": "nativo por latitud"},
    },
    "surface": {
        "bands": ["albedo", "ndvi", "landfrac"],
        "image": _surface,
        "params": {
            "albedo": [ALBEDO_ID, ALBEDO_BAND, ALBEDO_LEVEL, ALBEDO_STEP_DAYS], "snow": [SNOW_ID, SNOW_BAND],
            "ndvi": [NDVI_ID, NDVI_LEVEL], "landcover": [LC_ID, LC_BAND, EXCLUDED_LC], "dates": [DATE_START, DATE_END],
        },
    },
}


def parameters() -> dict:
    return {"grid": GRID, **{g: spec["params"] for g, spec in GROUPS.items()}}


def group_dir(group: str) -> Path:
    spec = {"grid": GRID, "bands": GROUPS[group]["bands"], "params": GROUPS[group]["params"]}
    return CACHE / f"{group}-{hashlib.sha1(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:10]}"


def group_image(group: str, band: Band) -> ee.Image:
    """Imagen del grupo para una franja: una celda de 5,09 km por píxel."""
    cell = ee.Projection("EPSG:4326", [band.dx, 0, -180, 0, -CELL_DEG, band.top])
    layers = GROUPS[group]["image"](band)
    return ee.Image.cat([layers[b].rename(b) for b in GROUPS[group]["bands"]]).reproject(cell).unmask(NODATA).toFloat()


# ---------------------------------------------------------------- pedidos


def compute(image: ee.Image, grid: dict, names: list[str], tries: int = 6) -> np.ndarray:
    """Pide los píxeles a Earth Engine: (filas, columnas, bandas), con NaN donde no hay dato."""
    for attempt in range(tries):
        try:
            raw = ee.data.computePixels({"expression": image, "fileFormat": "NUMPY_NDARRAY", "grid": grid})
            out = np.stack([raw[b].astype(np.float32) for b in names], axis=-1)
            out[out == NODATA] = np.nan
            return out
        except Exception as e:  # cuota, tiempo de espera o corte de red: esperar y reintentar
            if attempt == tries - 1:
                raise
            print(f"    reintento {attempt + 1}: {str(e)[:100]}", flush=True)
            time.sleep(min(60, 5 * 2**attempt))
    raise AssertionError


def chunk_grid(band: Band, c0: int, n: int) -> dict:
    return {
        "dimensions": {"width": n, "height": BAND_ROWS},
        "affineTransform": {"scaleX": band.dx, "shearX": 0, "translateX": -180.0 + c0 * band.dx,
                            "shearY": 0, "scaleY": -CELL_DEG, "translateY": band.top},
        "crsCode": "EPSG:4326",
    }


def chunk_path(group: str, band: Band, c0: int) -> Path:
    return group_dir(group) / f"b{band.k:03d}_c{c0:05d}.npy"


def load_chunk(band: Band, c0: int) -> dict[str, np.ndarray]:
    """Las bandas de un pedazo ya bajado: nombre -> (BAND_ROWS, n)."""
    out = {}
    for group, spec in GROUPS.items():
        a = np.load(chunk_path(group, band, c0))
        out.update({b: a[..., i] for i, b in enumerate(spec["bands"])})
    return out


# ---------------------------------------------------------------- qué pedazos bajar

SCREEN_DEG = 0.05
SCREEN_NDVI = 0.25  # más flojo que el umbral final, para no perder celdas
SCREEN_MIN = 25  # un pedazo se mide si tiene al menos esta cantidad de píxeles posibles (~600 km²)


def screening() -> np.ndarray:
    """Mapa global grueso (0,05°) de dónde puede haber celdas candidatas.

    Usa las pirámides de Earth Engine, así que es barato y aproximado. Solo
    decide qué pedazos vale la pena medir; la máscara definitiva se calcula
    después con las celdas de verdad.
    """
    spec = {"lat_max": LAT_MAX, "deg": SCREEN_DEG, "ndvi": SCREEN_NDVI, "surface": GROUPS["surface"]["params"]}
    path = CACHE / f"screening-{hashlib.sha1(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:10]}.npy"
    if path.exists():
        return np.load(path)
    maybe = _ndvi_mean().unmask(0).lt(SCREEN_NDVI).And(_land()).rename("maybe").unmask(0).toByte()
    w, h = round(360 / SCREEN_DEG), round(2 * LAT_MAX / SCREEN_DEG)
    out = np.zeros((h, w), dtype=bool)
    tile = 600  # un pedido global entero supera el límite de memoria de Earth Engine

    def work(origin: tuple[int, int]) -> None:
        r0, c0 = origin
        th, tw = min(tile, h - r0), min(tile, w - c0)
        grid = {
            "dimensions": {"width": tw, "height": th},
            "affineTransform": {"scaleX": SCREEN_DEG, "shearX": 0, "translateX": -180.0 + c0 * SCREEN_DEG,
                                "shearY": 0, "scaleY": -SCREEN_DEG, "translateY": LAT_MAX - r0 * SCREEN_DEG},
            "crsCode": "EPSG:4326",
        }
        out[r0 : r0 + th, c0 : c0 + tw] = compute(maybe, grid, ["maybe"])[..., 0] > 0

    with ThreadPoolExecutor(8) as pool:
        list(pool.map(work, [(r0, c0) for r0 in range(0, h, tile) for c0 in range(0, w, tile)]))
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, out)
    return out


def _screen_count(screen: np.ndarray, box: tuple[float, float, float, float]) -> int:
    w, s, e, n = box
    r0, r1 = max(int((LAT_MAX - n) / SCREEN_DEG), 0), min(int((LAT_MAX - s) / SCREEN_DEG) + 1, screen.shape[0])
    c0, c1 = max(int((w + 180.0) / SCREEN_DEG), 0), min(int((e + 180.0) / SCREEN_DEG) + 1, screen.shape[1])
    return int(screen[r0:r1, c0:c1].sum())


def circle_bbox(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    dlat = radius_km / (M_PER_DEG / 1000.0)
    dlon = dlat / max(math.cos(math.radians(lat)), 0.05)
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def _overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def plan(always: list[tuple[float, float, float, float]], region: tuple[float, float, float, float] | None = None
         ) -> list[tuple[Band, int, int]]:
    """Qué pedazos hay que medir.

    Sin region: los que pueden tener celdas candidatas según el mapa grueso,
    más los que tocan alguna de las cajas de `always` (los análogos conocidos).
    Con region (oeste, sur, este, norte): todos los que la tocan, para pruebas.
    """
    screen = None if region else screening()
    todo = []
    for band in bands():
        for c0, n in band.chunks():
            box = band.bbox(c0, n)
            if region:
                need = _overlap(box, region)
            else:
                need = _screen_count(screen, box) >= SCREEN_MIN or any(_overlap(box, a) for a in always)
            if need:
                todo.append((band, c0, n))
    return todo


# ---------------------------------------------------------------- descarga y cuota

LEDGER = CACHE / "cuota.json"


def _eecu_seconds(profile_ids: list[str]) -> float | None:
    """EECU-segundos de un pedido, según el perfil de cómputo de Earth Engine.

    El servicio de perfiles responde "no encontrado" más o menos la mitad de
    las veces, sin patrón. Se intenta tres veces por perfil; si no aparece,
    devuelve None y el pedido cuenta como no medido.
    """
    get = ee.ApiFunction.lookup("Profile.getProfiles")
    total = 0.0
    for pid in profile_ids:
        for attempt in range(3):
            try:
                text = get.call(ids=[pid]).getInfo()
                break
            except Exception:
                if attempt == 2:
                    return None
                time.sleep(2)
        for line in text.strip().split("\n")[1:]:
            try:
                total += float(line.split()[0])
            except (ValueError, IndexError):
                pass
    return total


def read_ledger() -> dict:
    led = {"requests": 0, "profiled": 0, "eecu_s_profiled": 0.0}
    if LEDGER.exists():
        led.update(json.loads(LEDGER.read_text()))
    return led


def quota_spent_hours() -> float:
    """Cuota gastada en pedidos de medición, estimada: el promedio de los pedidos
    cuyo perfil se pudo leer, por la cantidad total de pedidos."""
    led = read_ledger()
    return led["eecu_s_profiled"] / led["profiled"] * led["requests"] / 3600 if led["profiled"] else 0.0


def download(todo: list[tuple[Band, int, int]], workers: int = 8) -> None:
    """Baja al caché lo que falte, en paralelo, y anota la cuota gastada en data/earth_cache/cuota.json."""
    missing = [(g, b, c0, n) for b, c0, n in todo for g in GROUPS if not chunk_path(g, b, c0).exists()]
    missing.sort(key=lambda item: abs(item[1].lat_c))  # primero las latitudes bajas, donde están los desiertos
    print(f"Pedazos: {len(todo)} | pedidos por hacer: {len(missing)}", flush=True)
    if not missing:
        return
    images = {(g, b.k): group_image(g, b) for g, b in {(g, b) for g, b, _, _ in missing}}

    def work(item: tuple[str, Band, int, int]) -> float | None:
        group, band, c0, n = item
        ids: list[str] = []
        with ee.data.profiling(ids.append):
            out = compute(images[(group, band.k)], chunk_grid(band, c0, n), GROUPS[group]["bands"])
        path = chunk_path(group, band, c0)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.stem + ".tmp.npy")
        np.save(tmp, out)
        tmp.rename(path)
        return _eecu_seconds(ids)

    led = read_ledger()
    t0, done, failed = time.time(), 0, []
    with ThreadPoolExecutor(workers) as pool:
        futures = {pool.submit(work, item): item for item in missing}
        for f in as_completed(futures):
            done += 1
            if f.exception():
                group, band, c0, _ = futures[f]
                failed.append((group, band.k, c0, str(f.exception())[:120]))
            else:
                led["requests"] += 1
                if f.result() is not None:
                    led["profiled"] += 1
                    led["eecu_s_profiled"] = round(led["eecu_s_profiled"] + f.result(), 2)
            if done % 40 == 0 or done == len(missing):
                LEDGER.parent.mkdir(parents=True, exist_ok=True)
                LEDGER.write_text(json.dumps(led))
                print(f"  {done}/{len(missing)} en {time.time() - t0:.0f} s | cuota estimada {quota_spent_hours():.2f} EECU-h"
                      f" ({led['profiled']} de {led['requests']} pedidos medidos) | fallidos {len(failed)}", flush=True)
    if failed:
        raise RuntimeError(f"{len(failed)} pedidos fallaron; volvé a correr para reintentarlos. Ejemplos: {failed[:3]}")
