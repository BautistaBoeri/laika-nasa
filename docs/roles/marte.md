# Rol: Marte

Leé primero [el diseño](../diseno.md) y [los contratos](../contratos.md).

## Qué te toca

Bajar los mapas globales de Marte y medir, en cada sitio objetivo, las mismas variables que Nico mide en la Tierra. Esos números son contra los que se compara todo el planeta, así que de acá depende la validez del resultado.

- **Tu carpeta:** `mars/`
- **Recibís:** nada. Podés arrancar ya.
- **Entregás:** `mars/targets.json` (formato en los contratos)

## Datos

Los rasters van en `/data/` en la raíz del repo, que no se sube a git.

| Qué | Archivo | Tamaño |
|---|---|---|
| Elevación (MOLA, 463 m) | https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif | 2,1 GB |
| Albedo (TES, 7,4 km) | https://planetarymaps.usgs.gov/mosaic/Mars_MGS_TES_Albedo_mosaic_global_7410m.tif | 16 MB |

Los dos links responden (verificado el sábado 11:50). Fichas con la cita y la descripción:
[MOLA](https://astrogeology.usgs.gov/search/map/mars_mgs_mola_dem_463m) y
[albedo TES](https://astrogeology.usgs.gov/search/map/mars_mgs_tes_global_bolometric_albedo_map_7410m).

Para la segunda tanda:

- **Inercia térmica (TES, Putzig):** [ASU](https://www.mars.asu.edu/data/tes_putzigti/dayside2007) o [PSI](https://se.psi.edu/inertia/2007). No está verificado que el archivo venga georreferenciado; si no, es una grilla global simple y se ubica a mano.
- **Polvo (índice de cobertura de polvo de TES):** no encontramos todavía dónde se descarga.

## Sitios objetivo

| id | Sitio | Lat | Lon (este) | Por qué |
|---|---|---|---|---|
| `jezero` | Cráter Jezero | 18,44 | 77,45 | Donde está Perseverance; delta antiguo |
| `gale` | Cráter Gale | -4,59 | 137,44 | Donde está Curiosity |
| `arcadia` | Arcadia Planitia | ~47 | ~-176 | Candidata a base humana por hielo cerca de la superficie |

Jezero es obligatorio y va primero. Las coordenadas están de memoria: confirmalas con una fuente, sobre todo Arcadia, que es una región amplia y hay que elegir un punto.

## Pasos

1. **Arrancar las descargas** (la de 2 GB tarda).
2. **Acordar las variables con Nico** (30 min). Definición propuesta en los contratos.
3. **Mirar los archivos** con `gdalinfo` o `rasterio`: proyección, unidades, valor "sin dato", y si la elevación tiene factor de escala.
4. **Pendiente y relieve** desde MOLA, con `rasterio` y `numpy`:
   - pendiente en grados, píxel a píxel;
   - relieve: desvío estándar de la elevación en bloques de 5 km (unos 11 × 11 píxeles).
5. **Valor de cada sitio:** media y desvío de cada variable en un círculo de 25 km de radio.
6. **Estadísticas de todo Marte** por variable (media y desvío) para `mars_global`.
7. **Escribir `mars/targets.json`** y avisar en el grupo.
8. **Segunda tanda:** inercia térmica y polvo, y los otros sitios.

## Horarios

| Cuándo | Qué |
|---|---|
| Ya | Descargas en marcha |
| ~12:30 | Variables acordadas con Nico |
| 13:00 | Valores de Jezero, aunque sean provisorios, en `targets.json` |
| 15:00 | Valores definitivos de Jezero y estadísticas globales |
| 18:00 | Gale y Arcadia |
| 23:00 | Segunda tanda de variables |

## Cuidados

- **El tamaño del píxel no es 463 m en todos lados.** El mapa está en proyección cilíndrica: 463 m vale en el ecuador, y en sentido este-oeste se achica con el coseno de la latitud. En Jezero (18°) el error es de un 5 %; en Arcadia (47°) es de un 30 %. Hay que corregirlo al calcular la pendiente.
- **MOLA está interpolado.** El láser midió sobre líneas de órbita y entre línea y línea se rellenó. Cerca del ecuador la resolución real es más gruesa que 463 m. Es una limitación para declarar; anotá lo que veas.
- **Longitudes:** Marte se publica a veces de 0 a 360 y a veces de -180 a 180. El contrato usa grados este de -180 a 180.
- **El albedo de TES y el de MODIS no miden exactamente la misma banda** de luz. Se comparan igual, pero va a la lista de limitaciones.

## Para arrancar con tu Claude

> Tengo el rol Marte en este proyecto. Leé `docs/diseno.md`, `docs/contratos.md` y `docs/roles/marte.md`. Trabajá solo dentro de `mars/`; los rasters van en `/data/`. Empecemos por descargar los dos rasters e inspeccionarlos.
