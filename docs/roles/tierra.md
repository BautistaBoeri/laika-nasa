# Rol: Tierra (Nico)

Leé primero [el diseño](../diseno.md) y [los contratos](../contratos.md).

## Qué te toca

Medir toda la Tierra con las mismas variables que Marte, puntuar cada celda según cuánto se parece a cada sitio marciano, y entregarle a la página los 15 mejores lugares y la capa de similitud.

- **Tu carpeta:** `earth/`
- **Recibís:** `mars/targets.json` (de Marte) y `content/known_analogs.json` (de Contenido)
- **Entregás:** `web/data/sites.json`, `web/data/similarity_<target>.png` y, si llegás, `web/data/img/*.jpg`

## Lo que ya está andando

- Entorno virtual en `.venv` con `earthengine-api` instalado.
- Earth Engine autenticado en tu máquina. Proyecto: `laika-nasa`.
- Prueba hecha sobre un punto de Atacama: elevación y albedo responden bien.

```python
import ee
ee.Initialize(project='laika-nasa')
```

## Datos en Earth Engine

| Para qué | Colección | Notas |
|---|---|---|
| Elevación | `COPERNICUS/DEM/GLO30`, banda `DEM` | Es una colección: usar `.mosaic()`. Earth Engine avisa que está marcada como obsoleta; mirá en el catálogo cuál es el reemplazo. |
| Albedo | `MODIS/061/MCD43A3`, banda `Albedo_WSA_shortwave` | Viene multiplicado por 1000. Promediar varios años. Ojo con la nieve estacional. |
| Vegetación (máscara) | `MODIS/061/MOD13A2`, banda `NDVI` | Viene multiplicado por 10000. |
| Cobertura (máscara) | `MODIS/061/MCD12Q1`, banda `LC_Type1` | Para sacar agua y, según el sitio objetivo, hielo. |
| Temperatura (2ª tanda) | `MODIS/061/MOD11A2`, bandas `LST_Day_1km` y `LST_Night_1km` | En Kelvin, multiplicado por 50. |
| Lluvia (2ª tanda) | `UCSB-CHG/CHIRPS/DAILY` o ERA5-Land | CHIRPS solo cubre de 50°S a 50°N. |
| Polvo (2ª tanda) | `NASA/GSFC/MERRA/aer/2` | Verificar el nombre de la banda de polvo. |

Los nombres de colecciones y bandas de la segunda tanda están de memoria: confirmalos en el catálogo antes de usarlos.

## Pasos

1. **Acordar las variables con Marte** (30 min). La definición propuesta está en los contratos. Lo importante: degradar el modelo de elevación a 463 m *antes* de calcular pendiente y relieve.
2. **Probar en una región chica** (por ejemplo el noroeste argentino) las tres variables a 5 km. Mirar que los valores tengan sentido.
3. **Medir cuánta cuota gasta** esa prueba antes de ir al mundo entero. El proyecto tiene 150 horas de cómputo por mes. Si degradar el modelo de 30 m a escala global sale caro, usar uno que ya venga grueso (por ejemplo `USGS/GMTED2010_FULL`; verificar cobertura).
4. **Máscara:** quedarse con tierra firme sin vegetación (NDVI bajo) y sin agua.
5. **Similitud por variable:** `exp(-0.5 * ((tierra - marte) / sigma)^2)`, que da 1 si son iguales y baja hacia 0. `sigma` es la dispersión de esa variable; empezar con el `std` global de Marte que viene en `targets.json`.
6. **Similitud total:** promedio ponderado de las variables. Pesos iguales para empezar.
7. **Elegir los 15 mejores:** tomar las celdas de mayor puntaje, pero separadas al menos unos 300 km entre sí, para que no caigan las 15 en el mismo desierto.
8. **Validar:** ver qué puntaje sacan los análogos conocidos de `known_analogs.json`. Agregarlos al JSON con `known: true`. Después, sacarlos de la búsqueda de sitios nuevos.
9. **Exportar** `sites.json` y el PNG de la capa (en Web Mercator, ver contratos).
10. **Si llegás:** una imagen Sentinel-2 por sitio (`COPERNICUS/S2_SR_HARMONIZED`, con `getThumbURL`) guardada en `web/data/img/`.

## Horarios

| Cuándo | Qué |
|---|---|
| ~12:30 | Variables acordadas con Marte |
| 13:00 | Recibís análogos conocidos y valores provisorios de Jezero |
| 15:00 | Tres variables funcionando en una región |
| 18:00 | `sites.json` y capa de Jezero, mundo entero, en `web/data/` |
| 23:00 | Segunda tanda de variables, segundo sitio objetivo, validación |
| Dom 11:00 | Se congela el análisis |

## Cuidados

- La pendiente y el relieve dependen mucho de la resolución. Si no se igualan, el resultado no se puede defender.
- Si una variable de la segunda tanda no sale, se entrega sin ella y se dice.
- Guardar los parámetros usados (umbrales, pesos, fechas) en un archivo: van a hacer falta para la presentación.

## Para arrancar con tu Claude

> Soy Nico, tengo el rol Tierra en este proyecto. Leé `docs/diseno.md`, `docs/contratos.md` y `docs/roles/tierra.md`. Trabajá solo dentro de `earth/` y `web/data/`. Empecemos por el paso 2: las tres variables a 5 km en una región chica.
