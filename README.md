# laika-nasa

Buscador inverso de análogos de Marte en la Tierra, para NASA Space Apps 2026.
En vez de elegir un lugar que "se parece a Marte", medimos un sitio marciano
real (el cráter Jezero) y le preguntamos a toda la Tierra qué celdas de 5 km se
le parecen en pendiente, relieve local y albedo.

El diseño está en [docs/diseno.md](docs/diseno.md) y los formatos de los
archivos que conectan las partes, en [docs/contratos.md](docs/contratos.md).

## Preparar la máquina

Hace falta Python 3.10 o más y unos 3 GB de disco.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/earthengine authenticate     # una vez; la cuenta tiene que estar en el proyecto laika-nasa
```

## Correr cada parte

Todo se corre desde la raíz del repo.

| Parte | Comando | Qué genera |
| --- | --- | --- |
| Marte | `.venv/bin/python mars/build_targets.py` | `mars/targets.json` |
| Tierra | `.venv/bin/python earth/build_sites.py` | `web/data/sites.json`, `web/data/similarity_jezero.png`, `earth/validacion.json`, `earth/parametros.json` |
| Web | `python3 -m http.server 8000 --directory web` | la página en <http://localhost:8000> |
| Prueba | `.venv/bin/python earth/test_similarity.py` | prueba de la función de similitud |

**Marte.** La primera vez baja los rasters de MOLA (2,1 GB) y TES (16 MB) a
`data/`. Después tarda medio minuto y usa cerca de 1 GB de memoria.

**Tierra.** La primera vez mide el planeta en Google Earth Engine: unos 15
minutos y cerca de 8 horas de cómputo de la cuota mensual de 150. El resultado
queda en `data/earth_cache/`, así que volver a correr tarda segundos y no gasta
cuota mientras no cambien los parámetros de `earth/measure.py`. Si la máquina
se suspende, la medición se frena; al volver a correr sigue donde quedó.

Para probar en una región chica sin tocar `web/`:

```bash
.venv/bin/python earth/build_sites.py --region -69 -27 -65 -22   # oeste sur este norte
```

**Web.** Es estática: HTML, CSS y JavaScript sin compilar, con Leaflet desde un
CDN y mapa base de NASA GIBS. Lee `web/data/sites.json` y, si existe,
`web/data/textos.json`. Hay que abrirla desde un servidor, no con doble clic.

## Carpetas

| Carpeta | Qué hay |
| --- | --- |
| `mars/` | Medición de los sitios de Marte |
| `earth/` | Medición de la Tierra en Earth Engine, similitud y elección de sitios |
| `content/` | Análogos ya conocidos (`known_analogs.json`) |
| `web/` | La página; en `web/data/` están los datos que lee |
| `data/` | Rasters y caché de Earth Engine. No va a git |
| `docs/` | Diseño, contratos y guías por rol |

## Cómo se mide

- **Misma resolución en los dos planetas.** El modelo de elevación terrestre
  (Copernicus GLO-30) se promedia a píxeles de 463 m, la resolución de MOLA,
  antes de calcular pendiente y relieve. La pendiente sale de diferencias
  centrales y la celda de análisis tiene 11 x 11 píxeles (5,09 km).
- **Píxeles de tamaño real.** En Marte se corrige el coseno de la latitud de la
  proyección cilíndrica. En la Tierra el planeta se parte en franjas de 1,8° de
  latitud, cada una con su ancho de píxel, para que la celda mida 5 km en todas
  partes.
- **Dónde se busca.** Tierra firme con NDVI medio menor que 0,15 y sin agua,
  hielo permanente ni ciudad.
- **Similitud.** `exp(-0.5 * ((tierra - marte) / sigma)^2)` por variable, con
  `sigma` igual al desvío de esa variable en todo Marte; la total es el
  promedio.
- **Sitios.** Las 15 celdas de mayor puntaje separadas al menos 300 km, fuera
  del radio de los análogos conocidos.
- **Validación.** Los análogos conocidos no entran en la búsqueda. Su puntaje es
  el promedio de las celdas a menos de 25 km del punto, el mismo círculo con que
  se midió Jezero. El detalle queda en `earth/validacion.json`.

Los umbrales, pesos, fechas y datos usados en cada corrida quedan en
`earth/parametros.json`.

## Fuentes

- Coordenadas de los análogos conocidos: datos geográficos de Wikipedia. El
  campo `source` de cada uno enlaza un trabajo o nota que respalda su uso como
  análogo.
- Jezero: punto de aterrizaje de Perseverance, 18,44° N 77,45° E.
- Marte: [MOLA](https://astrogeology.usgs.gov/search/map/mars_mgs_mola_dem_463m)
  y [albedo TES](https://astrogeology.usgs.gov/search/map/mars_mgs_tes_global_bolometric_albedo_map_7410m), USGS.
- Tierra: Copernicus DEM GLO-30 y productos MODIS MCD43A3, MCD43A2, MOD13A2 y
  MCD12Q1, en Google Earth Engine.
