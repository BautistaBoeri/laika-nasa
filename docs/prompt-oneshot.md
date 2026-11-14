# Prompt: construir la primera versión completa de una sola pasada

Pegale este archivo entero a Claude Code, abierto en la raíz del repo `laika-nasa`.

---

Vas a construir, de punta a punta y sin detenerte a pedir confirmación, la primera versión funcional de nuestro proyecto para NASA Space Apps 2026. Somos cuatro estudiantes de Ingeniería Informática (FIUBA) y entregamos el domingo 15 de noviembre de 2026 a las 15:00, hora de Buenos Aires. Respondé en español rioplatense.

## Qué estamos haciendo

El challenge es "Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars": usar datos abiertos para encontrar lugares de la Tierra que sirvan como análogos de sitios de la Luna o Marte, justificando la analogía con datos y explicando dónde se rompe.

Nuestra idea es una **búsqueda inversa**: en vez de elegir un lugar que "se parece a Marte", medimos un sitio marciano real con variables numéricas y le preguntamos a toda la Tierra qué celdas se le parecen, variable por variable. Lo que quede arriba en el ranking y no sea un análogo ya conocido es nuestro hallazgo. El jurado evalúa impacto, creatividad, validez técnica, relevancia respecto del enunciado y presentación; la validez depende de que las variables se midan igual en los dos planetas.

Antes de escribir código leé `docs/diseno.md` y `docs/contratos.md`. El segundo fija los formatos de los archivos que conectan las partes: respetalos tal cual, porque otras personas del equipo trabajan contra ellos. Los documentos de `docs/roles/` tienen detalle adicional de cada parte.

## Qué tiene que existir cuando termines

Una página web estática que, abierta en el navegador, muestra un mapa del mundo con unos 15 puntos análogos al cráter Jezero calculados con datos reales, y una vista de detalle por punto con el puntaje de cada variable. Para llegar ahí hacen falta cuatro piezas:

1. **`mars/`**: un script de Python que baja los rasters de Marte a `/data/` (si no están), mide las variables en Jezero y escribe `mars/targets.json`.
2. **`content/known_analogs.json`**: unos 15 análogos de Marte ya conocidos, con coordenadas, radio y un link de respaldo.
3. **`earth/`**: un script de Python que usa Google Earth Engine para medir las mismas variables en toda la Tierra, calcular la similitud, elegir los mejores sitios y escribir `web/data/sites.json` y `web/data/similarity_jezero.png`.
4. **`web/`**: la página, que lee esos archivos.

Alcance de esta versión: un solo sitio objetivo (Jezero) y tres variables (pendiente, relieve local, albedo). Gale, Arcadia y las variables térmica, de aridez y de polvo vienen después. Dejá el código de forma que agregar un sitio o una variable sea agregar una entrada, sin generalizar más que eso.

## Requisitos de la máquina

- Python 3.10 o superior. Creá un entorno virtual en `.venv` e instalá ahí lo que necesites (`earthengine-api`, `rasterio`, `numpy` y poco más).
- Earth Engine: el proyecto de Google Cloud es `laika-nasa`. Se inicializa con `ee.Initialize(project='laika-nasa')`.
- Unos 3 GB de disco libres para los rasters.

Lo primero que tenés que hacer es probar que Earth Engine responde. Si falla por falta de credenciales, no podés resolverlo vos: frená y decile a la persona que corra `.venv/bin/earthengine authenticate` en una terminal y que su cuenta de Google tiene que estar agregada al proyecto `laika-nasa`. Mientras tanto podés avanzar con Marte y con la web, que no dependen de eso.

## Datos

**Marte** (descarga directa, sin cuenta; los dos links fueron verificados):

- Elevación MOLA, 463 m por píxel, 2,1 GB: `https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif`
- Albedo TES, 7,4 km por píxel, 16 MB: `https://planetarymaps.usgs.gov/mosaic/Mars_MGS_TES_Albedo_mosaic_global_7410m.tif`
- Jezero: 18,44° N, 77,45° E (zona de aterrizaje de Perseverance). Confirmá la coordenada con una fuente.

**Tierra** (en Earth Engine):

- Elevación: `COPERNICUS/DEM/GLO30`, banda `DEM`. Es una colección, se usa con `.mosaic()`. Earth Engine avisa que está marcada como obsoleta; fijate en el catálogo si hay reemplazo y usalo.
- Albedo: `MODIS/061/MCD43A3`, banda `Albedo_WSA_shortwave`, multiplicado por 1000.
- Vegetación, para la máscara: `MODIS/061/MOD13A2`, banda `NDVI`, multiplicado por 10000.
- Cobertura, para sacar el agua: `MODIS/061/MCD12Q1`, banda `LC_Type1`.

## Cómo se calcula

Las definiciones exactas están en `docs/contratos.md`. Lo que no es obvio y ya sabemos:

- **Igualar la resolución antes de medir.** La pendiente y el relieve dependen de la resolución del modelo de elevación. El de Marte tiene 463 m por píxel y el de la Tierra 30 m; si no se degrada el terrestre a 463 m antes de calcular, la Tierra da siempre más empinada y la comparación no vale. Esta es la decisión técnica más importante del proyecto.
- **El píxel de Marte no mide 463 m en todos lados.** El raster está en proyección cilíndrica: en sentido este-oeste el tamaño real se achica con el coseno de la latitud. Corregilo al calcular la pendiente.
- **Revisá los rasters antes de usarlos**: proyección, unidades, valor "sin dato" y si la elevación trae factor de escala. No lo des por sabido.
- **Grilla de análisis de unos 5 km**, solo sobre tierra firme sin vegetación (NDVI bajo) y sin agua.
- **Similitud por variable:** `exp(-0.5 * ((tierra - marte) / sigma)^2)`, donde `sigma` es el desvío global de esa variable en Marte. Da 1 cuando coinciden y cae hacia 0.
- **Similitud total:** promedio de las variables con pesos iguales.
- **Elegir los sitios:** las celdas de mayor puntaje, separadas entre sí por al menos 300 km, para que no caigan todas en el mismo desierto.
- **Validación:** los análogos conocidos no entran en el cálculo. Después de calcular, medí qué puntaje saca cada uno y en qué percentil del planeta queda. Incluilos en `sites.json` con `known: true` y excluí sus alrededores al elegir los sitios nuevos.

Sobre Earth Engine: el proyecto tiene una cuota mensual de 150 horas de cómputo. Probá primero todo el proceso en una región chica (por ejemplo el noroeste argentino), mirá que los valores tengan sentido y recién después corré el mundo entero. Si degradar el modelo de 30 m a escala global resulta muy lento o caro, usá un modelo de elevación que ya venga más grueso y dejalo anotado. Las descargas directas de Earth Engine tienen límite de tamaño: un raster global de 5 km no baja de una sola vez, así que partilo, bajá la resolución de lo que descargás o resolvé la selección de los mejores sitios del lado del servidor.

## La página

Sin backend y sin paso de compilación: HTML, CSS y JavaScript que leen `web/data/sites.json` y, si existe, `web/data/textos.json`. Usá Leaflet desde un CDN.

- Mapa del mundo con fondo oscuro o satelital, con la atribución que pida el proveedor.
- Un punto por sitio, con color según el puntaje. Los `known: true` en otro color, con leyenda.
- Un control para prender y apagar la capa de similitud. El PNG tiene que estar en Web Mercator (EPSG:3857), con longitud de -180 a 180 y latitud de -85 a 85; en latitud y longitud plana queda corrido respecto del mapa.
- Al tocar un punto, un panel con: nombre y país si están en `textos.json` (si no, las coordenadas), puntaje total, y una barra por variable con el porcentaje y el valor de la Tierra junto al de Marte.
- La página dibuja las variables que vengan en el JSON, no una lista fija, y funciona aunque falten el texto o la imagen de un sitio.
- Una sección breve "Cómo funciona" y otra "Límites", que diga que la Tierra no reproduce la gravedad, la presión atmosférica, la composición del aire ni la radiación de Marte.
- Tiene que verse bien proyectada: prolija, legible de lejos y que cargue rápido.

## Cómo saber que terminaste

- Los dos scripts corren de cero con un comando cada uno y generan sus archivos.
- `mars/targets.json` y `web/data/sites.json` cumplen el formato de `docs/contratos.md`.
- Abriste la página en un navegador, con un servidor local, y viste el mapa, los puntos, la capa y el panel de detalle funcionando con los datos reales.
- Los valores son creíbles: pendientes de unos pocos grados en llanuras, albedos entre 0 y 1, y ningún sitio elegido en medio del mar o de una selva.
- Hay una prueba mínima de la función de similitud (iguales dan 1, muy distintos dan cerca de 0).
- Un `README.md` corto en la raíz explica cómo correr cada parte.

## Reglas de trabajo

- No pidas confirmación para decisiones reversibles: elegí, anotá el motivo en una línea y seguí. Frená solo si falta algo que únicamente la persona puede dar, como la autenticación.
- No inventes datos. Si una fuente no responde o un valor no cierra, decilo; un resultado parcial y honesto sirve más que uno completo y dudoso.
- Los análogos conocidos necesitan coordenadas y fuente reales: buscalos, no los pongas de memoria.
- No hagas `git push`. Commits locales, chicos y descriptivos.
- No agregues la Luna, aprendizaje automático, base de datos ni backend.

## Qué reportar al final

Un resumen corto con:

- qué quedó funcionando y cómo se corre;
- los cinco mejores sitios nuevos, con coordenadas y puntaje;
- qué puntaje sacaron los análogos conocidos, es decir, si el método los encuentra o no;
- qué decisiones tomaste que el equipo debería revisar;
- qué no pudiste verificar y cuánta cuota de Earth Engine se gastó.
