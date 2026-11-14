"""Promedios por zona: para cada celda, la media de un campo en el círculo que la rodea.

Sirve para puntuar una zona de la Tierra igual que se midió el sitio marciano
(media de las celdas en un círculo de radius_km), en vez de una celda suelta.
"""

from __future__ import annotations

import numpy as np

import measure as m


def zone_means(cells: dict[str, np.ndarray], fields: dict[str, np.ndarray], radius_km: float
               ) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Media ponderada por área de cada campo en el círculo de radius_km de cada celda.

    Devuelve los promedios (un arreglo por campo, alineado con `cells`) y la
    cobertura: qué fracción de las celdas del círculo es medible.
    """
    reach = int(radius_km // m.CELL_KM)
    offsets = [(dr, dc) for dr in range(-reach, reach + 1) for dc in range(-reach, reach + 1)
               if (dr * dr + dc * dc) * m.CELL_KM**2 <= radius_km**2]
    all_bands = m.bands()
    names = list(fields)
    order = np.argsort(cells["band"], kind="stable")
    starts = np.searchsorted(cells["band"][order], np.arange(len(all_bands) + 1))

    def grids(k: int) -> np.ndarray | None:
        """Franja k como grilla densa: capa 0 = peso, después peso * campo. None si está vacía."""
        if not 0 <= k < len(all_bands) or starts[k] == starts[k + 1]:
            return None
        idx = order[starts[k] : starts[k + 1]]
        g = np.zeros((len(names) + 1, m.BAND_ROWS, all_bands[k].ncols), dtype=np.float32)
        r, c, w = cells["row"][idx], cells["col"][idx], cells["w"][idx]
        g[0, r, c] = w
        for n, name in enumerate(names):
            g[n + 1, r, c] = w * fields[name][idx]
        return g

    out = {name: np.full(cells["lat"].size, np.nan, dtype=np.float32) for name in names}
    coverage = np.zeros(cells["lat"].size, dtype=np.float32)
    cache: dict[int, np.ndarray | None] = {}
    for k in range(len(all_bands)):
        for j in (k - 1, k, k + 1):
            if j not in cache:
                cache[j] = grids(j)
        cache.pop(k - 2, None)
        centre = cache[k]
        if centre is None:
            continue
        band = all_bands[k]
        # filas de las franjas vecinas, llevadas a las columnas de esta franja
        ext = np.zeros((centre.shape[0], m.BAND_ROWS + 2 * reach, band.ncols), dtype=np.float32)
        ext[:, reach : reach + m.BAND_ROWS] = centre
        lon = band.lons(0, band.ncols)
        for j, rows, where in ((k - 1, slice(m.BAND_ROWS - reach, m.BAND_ROWS), slice(0, reach)),
                               (k + 1, slice(0, reach), slice(reach + m.BAND_ROWS, None))):
            if cache[j] is not None:
                cols = np.minimum(((lon + 180.0) / all_bands[j].dx).astype(np.int64), all_bands[j].ncols - 1)
                ext[:, where] = cache[j][:, rows][:, :, cols]
        total = np.zeros_like(centre)
        for dr, dc in offsets:
            total += np.roll(ext[:, reach + dr : reach + dr + m.BAND_ROWS], -dc, axis=2)
        idx = order[starts[k] : starts[k + 1]]
        r, c = cells["row"][idx], cells["col"][idx]
        weight = total[0, r, c]
        coverage[idx] = weight / len(offsets)
        for n, name in enumerate(names):
            out[name][idx] = total[n + 1, r, c] / weight
    return out, coverage
