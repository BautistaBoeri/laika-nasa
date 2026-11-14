"""Dibuja la capa de similitud como PNG en Web Mercator (formato en docs/contratos.md).

Límites: longitud de -180 a 180, latitud de -85 a 85. Transparente donde no
hay celda candidata.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image

import measure as m

WIDTH = 4096
LAT_LIMIT = 85.0
Y_LIMIT = math.log(math.tan(math.pi / 4 + math.radians(LAT_LIMIT) / 2))  # y de Mercator en el borde
HEIGHT = round(WIDTH * Y_LIMIT / math.pi)
SUPER = 2  # cada píxel promedia SUPER x SUPER muestras, para no saltearse celdas

# Escala de color: un solo tono, de oscuro (poco parecido) a claro (muy parecido).
# web/app.js usa estos mismos valores para la leyenda y los puntos: cambiarlos juntos.
RAMP = ["#3b0e00", "#5d1c00", "#822a00", "#a83900", "#cb4e19", "#e96a3a", "#ff8c63", "#ffb9a0", "#ffe0d6"]
SCALE_MIN, SCALE_MAX = 0.5, 1.0


def palette() -> list[int]:
    """Paleta de 256 colores: el índice 0 es transparente, del 1 al 255 va la rampa."""
    stops = np.array([[int(h[i : i + 2], 16) for i in (1, 3, 5)] for h in RAMP], dtype=float)
    x = np.linspace(0, len(RAMP) - 1, 255)
    rgb = np.stack([np.interp(x, np.arange(len(RAMP)), stops[:, c]) for c in range(3)], axis=1).round().astype(int)
    return [0, 0, 0] + rgb.ravel().tolist()


def render_layer(cells: dict[str, np.ndarray], score: np.ndarray, path: Path) -> None:
    """Escribe el PNG. `score` tiene un valor por celda de `cells`, o NaN si no se pinta."""
    all_bands = m.bands()
    dense = {}
    for k in np.unique(cells["band"]):
        grid = np.full((m.BAND_ROWS, all_bands[k].ncols), np.nan, dtype=np.float32)
        sel = cells["band"] == k
        grid[cells["row"][sel], cells["col"][sel]] = score[sel]
        dense[int(k)] = grid

    # latitud de cada fila de muestras y longitud de cada columna de muestras
    sub_h, sub_w = HEIGHT * SUPER, WIDTH * SUPER
    y = Y_LIMIT * (1 - 2 * (np.arange(sub_h) + 0.5) / sub_h)
    lat = np.degrees(2 * np.arctan(np.exp(y)) - math.pi / 2)
    lon = -180.0 + 360.0 * (np.arange(sub_w) + 0.5) / sub_w
    band_h = m.BAND_ROWS * m.CELL_DEG
    cols = {k: np.minimum(((lon + 180.0) / all_bands[k].dx).astype(np.int64), all_bands[k].ncols - 1) for k in dense}

    total = np.zeros((HEIGHT, WIDTH), dtype=np.float32)
    count = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
    for i in range(sub_h):
        k = int((m.LAT_MAX - lat[i]) // band_h)
        if k not in dense:
            continue
        row = int((all_bands[k].top - lat[i]) / m.CELL_DEG)
        if not 0 <= row < m.BAND_ROWS:
            continue
        v = dense[k][row, cols[k]].reshape(WIDTH, SUPER)
        ok = ~np.isnan(v)
        total[i // SUPER] += np.where(ok, v, 0.0).sum(axis=1)
        count[i // SUPER] += ok.sum(axis=1).astype(np.uint8)

    index = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
    has = count > 0
    mean = total[has] / count[has]
    t = np.clip((mean - SCALE_MIN) / (SCALE_MAX - SCALE_MIN), 0.0, 1.0)
    index[has] = 1 + np.round(t * 254).astype(np.uint8)

    image = Image.fromarray(index, mode="P")
    image.putpalette(palette())
    image.save(path, optimize=True, transparency=0)
    print(f"Capa {path.name}: {WIDTH} x {HEIGHT} px, {100 * has.mean():.1f} % con dato, {path.stat().st_size / 1e6:.2f} MB")
