"""
Baja una imagen Sentinel-2 (color real) de cada sitio de web/data/sites*.json.

  python earth/imagenes.py            # baja las que falten
  python earth/imagenes.py --todas    # las vuelve a bajar todas

Deja web/data/img/<id del sitio>.jpg. La página busca la imagen por ese nombre
y, si no existe, muestra el mapa de ubicación.
"""
import json
import math
import sys
import urllib.request
from pathlib import Path

import ee

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "web" / "data" / "img"
ANCHO_KM, ALTO_KM = 32, 20          # 16:10, como el recuadro del panel
TAMANO = "640x400"
PERIODO = ("2023-01-01", "2025-01-01")


def caja(lat, lon):
    """Rectángulo de ANCHO_KM x ALTO_KM centrado en el sitio, en grados."""
    dh = ALTO_KM / 2 / 111.32
    dw = ANCHO_KM / 2 / (111.32 * max(math.cos(math.radians(lat)), 0.05))
    return ee.Geometry.Rectangle([lon - dw, lat - dh, lon + dw, lat + dh], None, False)


def url_imagen(lat, lon):
    region = caja(lat, lon)
    s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
          .filterBounds(region).filterDate(*PERIODO)
          .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 10)))
    if abs(lat) > 50:  # en latitudes altas, solo el verano local: el resto del año es nieve
        meses = (7, 8) if lat > 0 else (1, 2)
        s2 = s2.filter(ee.Filter.calendarRange(*meses, "month"))
    # la mediana de dos años saca nubes y sombras sueltas. Donde se cruzan varias
    # pasadas hay más de mil imágenes y Earth Engine rechaza el pedido (error 400):
    # alcanza con las 200 más despejadas.
    img = (s2.sort("CLOUDY_PIXEL_PERCENTAGE").limit(200)
           .median().select(["B4", "B3", "B2"]))
    # Web Mercator conserva la proporción 16:10 en cualquier latitud
    return img.getThumbURL({"region": region, "dimensions": TAMANO, "crs": "EPSG:3857",
                            "format": "jpg", "min": 0, "max": 3500, "gamma": 1.3})


def main():
    ee.Initialize(project="laika-nasa")
    SALIDA.mkdir(parents=True, exist_ok=True)
    # sites.json y sus variantes (sites_v2.json, ...): la foto se comparte por id
    sitios = {s["id"]: s
              for archivo in sorted((RAIZ / "web" / "data").glob("sites*.json"))
              for t in json.loads(archivo.read_text(encoding="utf-8"))["targets"]
              for s in t["sites"]}
    solo = [a for a in sys.argv[1:] if not a.startswith("--")]
    for id_, s in sorted(sitios.items()):
        ruta = SALIDA / f"{id_}.jpg"
        if solo and id_ not in solo:
            continue
        if ruta.exists() and "--todas" not in sys.argv and not solo:
            continue
        try:
            with urllib.request.urlopen(url_imagen(s["lat"], s["lon"]), timeout=120) as r:
                ruta.write_bytes(r.read())
            print("ok   ", id_, ruta.stat().st_size // 1024, "KB")
        except Exception as e:  # un sitio sin imágenes (polos, nubes) no frena al resto
            print("falla", id_, type(e).__name__, str(e)[:120])


if __name__ == "__main__":
    main()
