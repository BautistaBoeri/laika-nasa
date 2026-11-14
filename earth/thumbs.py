"""Imagen satelital de cada sitio para la ficha (campo opcional `image` de sites.json).

Mediana de las escenas Sentinel-2 con pocas nubes de 2024 y 2025, en color
real, sobre un recuadro de 40 x 25 km centrado en el sitio. Si una imagen ya
está en web/data/img/ no se vuelve a pedir.
"""

from __future__ import annotations

import io
import math
import urllib.request
from pathlib import Path

import ee
import numpy as np
from PIL import Image

import measure as m

S2 = "COPERNICUS/S2_SR_HARMONIZED"
DATES = ("2024-01-01", "2026-01-01")
MAX_CLOUD = 10  # porcentaje de nubes de la escena
MAX_SNOW = 5  # porcentaje de nieve o hielo de la escena
MAX_EMPTY = 0.3  # si más de esta fracción de la imagen viene sin dato, no se usa
WIDTH_KM, HEIGHT_KM = 40.0, 25.0
SIZE = "640x400"
VIS = {"bands": ["B4", "B3", "B2"], "min": 200, "max": 4500, "gamma": 1.4}


def site_image(site: dict, web_data: Path) -> str | None:
    """Baja la imagen del sitio si falta. Devuelve la ruta relativa a web/, o None si no hay escenas."""
    path = web_data / "img" / f"{site['id']}.jpg"
    if not path.exists():
        km_per_deg = m.M_PER_DEG / 1000.0
        dlat = HEIGHT_KM / 2 / km_per_deg
        dlon = WIDTH_KM / 2 / (km_per_deg * math.cos(math.radians(site["lat"])))
        box = ee.Geometry.Rectangle([site["lon"] - dlon, site["lat"] - dlat, site["lon"] + dlon, site["lat"] + dlat], None, False)
        scenes = (ee.ImageCollection(S2).filterBounds(box).filterDate(*DATES)
                  .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", MAX_CLOUD)).select(VIS["bands"]))
        # Arriba, la mediana de las escenas sin nieve (si no, en latitudes altas sale
        # todo blanco); donde no hay ninguna, la mediana de todas.
        clear = scenes.filter(ee.Filter.lt("SNOW_ICE_PERCENTAGE", MAX_SNOW))
        everything = scenes.median()
        image = ee.Image(ee.Algorithms.If(clear.size().gt(0), clear.median().unmask(everything, False), everything))
        try:
            url = image.visualize(**VIS).getThumbURL({"region": box, "dimensions": SIZE, "crs": "EPSG:3857", "format": "jpg"})
            data = urllib.request.urlopen(url, timeout=120).read()
        except Exception as e:  # sin escenas o pedido fallido: la ficha sale sin foto
            print(f"  sin imagen para {site['id']}: {str(e)[:80]}")
            return None
        picture = np.asarray(Image.open(io.BytesIO(data)).convert("RGB"))
        if (picture.max(axis=2) < 8).mean() > MAX_EMPTY:
            print(f"  sin imagen para {site['id']}: Sentinel-2 no cubre la zona")
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return f"data/img/{path.name}"
