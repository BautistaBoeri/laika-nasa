# Buscador inverso de análogos de Marte en la Tierra

Diseño corto para NASA Space Apps 2026. Entrega: domingo 15/11 a las 15:00 (apuntamos a subir todo a las 14:30).

## Qué hacemos y por qué

En vez de elegir un lugar "que se parece a Marte", partimos de sitios marcianos reales, los describimos con números y le preguntamos a toda la Tierra qué lugares se les parecen, variable por variable. Lo que aparezca arriba en el ranking y no sea un análogo ya conocido es nuestro hallazgo.

- **Sitios objetivo en Marte:** cráter Jezero (Perseverance) y uno o dos más a elegir el sábado a la tarde (candidatos: Gale, Arcadia Planitia).
- **Entregable:** una página web estática, dinámica, sencilla y visualmente llamativa (ver "La página").

## La página

```
┌───────────────────────────────────────────────┐
│  Análogos de:  [ Jezero ▾ ]   [capa similitud]│
│        ·  mapa del mundo  ·     ●             │
│     ●                        ○                │
│              ●        ●                       │
└───────────────────────────────────────────────┘
        click en un punto ↓
┌───────────────────────────────────────────────┐
│  Nombre del sitio, país         Similitud 82% │
│  [imagen satelital]                           │
│  Pendiente    ████████░░  84%                 │
│  Rugosidad    ███████░░░  71%                 │
│  Albedo       █████████░  91%                 │
│  Por qué se parece · Dónde se rompe ·         │
│  Para qué serviría                            │
└───────────────────────────────────────────────┘
```

- **Mapa del mundo con puntos clickeables:** unos 15 sitios análogos por sitio objetivo de Marte, con un selector para cambiar de sitio objetivo.
- **Análogos conocidos en otro color** (○): muestran la validación del método a la vista.
- **Capa de similitud continua**, que se prende y apaga: prueba que la búsqueda fue global y no a mano.
- **Vista de detalle al hacer click:** índice de similitud total y una barra por variable, con el valor del sitio terrestre al lado del valor marciano.
- **Texto:** los ~15 puntos muestran barras y números generados automáticamente desde los datos; solo los 3 mejores tienen explicación redactada y revisada a mano (por qué se parece, dónde se rompe la analogía, para qué serviría). Se itera después.
- **Datos:** el análisis exporta un único archivo JSON con los sitios, sus puntajes y valores; la página lo lee. La capa continua se exporta como imagen.

## Qué no hacemos

- La Luna: muy pocas variables comparables con la Tierra. Solo si sobra tiempo.
- Machine learning o similitud de imágenes: el enunciado pide ir más allá de lo visual.
- Backend propio: todo el cómputo corre en Earth Engine y la web es estática.

## Alternativas consideradas

| Enfoque | Por qué sí / por qué no |
|---|---|
| **A. Búsqueda global con Earth Engine (elegido)** | Responde a "search globally and systematically"; el método es la novedad. Depende de un servicio externo. |
| B. Búsqueda solo en Argentina, rasters locales | Sin dependencias externas, pero deja de ser global. Es el plan de respaldo: el código de similitud es el mismo. |
| C. Un sitio elegido a mano | Sin método que defender; poca creatividad. Descartado. |

**Punto de decisión: sábado 13:00.** Si Earth Engine no devuelve un mapa de prueba, pasamos a B.

## Variables

Todo se lleva a una grilla de unos 5 km sobre tierra sin vegetación ni hielo ni agua.

| Dimensión | Marte | Tierra (Earth Engine) | Cómo se compara |
|---|---|---|---|
| Pendiente y rugosidad | MOLA 463 m (USGS) | Copernicus DEM, remuestreado a 463 m antes de calcular | Unidades físicas |
| Albedo | TES albedo bolométrico 7,4 km (USGS) | MODIS MCD43A3 | Unidades físicas |
| Comportamiento térmico | Inercia térmica TES (Putzig, ASU/PSI) | MODIS LST día menos noche, combinado con albedo | Percentil dentro de cada planeta |
| Aridez | Se asume extrema | Precipitación anual (CHIRPS o ERA5-Land) | Puntaje directo: más seco, mejor |
| Polvo | Índice de cobertura de polvo TES (si se consigue) | Polvo en columna MERRA-2 | Percentil dentro de cada planeta |

Orden de construcción: primero pendiente, rugosidad y albedo de punta a punta; las demás se suman después. Si una variable no llega, se entrega sin ella y se dice.

## Similitud

- Por dimensión: puntaje de 0 a 1 según la diferencia entre la celda terrestre y el sitio marciano, normalizada por la dispersión de esa variable.
- Total: promedio ponderado, con pesos visibles y ajustables en la página.
- El mapa siempre permite ver cada dimensión por separado: un sitio puede ser buen análogo topográfico y malo térmico, y eso es parte del resultado.

## Validación

Los análogos conocidos (Atacama, Valles Secos antárticos, Islandia, Hawái, Haughton, Death Valley, entre otros) no se le informan al método. Si aparecen altos en el ranking, el método funciona; después se enmascaran para mostrar solo los sitios nuevos. Si no aparecen, lo reportamos y revisamos las variables.

## Limitaciones que vamos a declarar

- Gravedad, presión atmosférica, radiación y composición del aire no se pueden reproducir en la Tierra; cada ficha lo dice explícitamente.
- La dimensión térmica y la de polvo comparan posición relativa dentro de cada planeta, no valores absolutos.
- Resolución de 5 km: sirve para encontrar regiones, no para elegir un punto de ensayo.
- Sin mineralogía en la primera versión.

## Ficha de cada sitio nuevo

Ubicación y acceso, puntaje por dimensión, en qué se parece, dónde se rompe la analogía, y para qué serviría (probar movilidad de rovers, instrumentos, operaciones, búsqueda de recursos).

## Reparto y horarios

| Persona | Responsabilidad |
|---|---|
| 1 | Variables terrestres en Earth Engine |
| 2 | Rasters de Marte y vectores de los sitios objetivo |
| 3 | Página web: mapa, puntos y vista de detalle |
| 4 | Lista de análogos conocidos, texto de los 3 mejores sitios, limitaciones y presentación |

| Cuándo | Qué tiene que estar |
|---|---|
| Sáb 13:00 | Mapa de prueba desde Earth Engine y MOLA descargado. Decisión A o B. |
| Sáb 18:00 | Primera versión de punta a punta con pendiente, rugosidad y albedo para Jezero, visible en la web |
| Sáb 23:00 | Resto de las variables, segundo sitio objetivo, validación con análogos conocidos |
| Dom 08:00 a 11:00 | Top 3 de sitios nuevos y sus fichas; se congela el análisis |
| Dom 11:00 a 13:30 | Presentación, demo grabada, página del proyecto, README |
| Dom 13:30 a 14:30 | Margen y envío |

## Cómo responde a los criterios

- **Impact:** herramienta reutilizable para cualquier sitio objetivo, más sitios concretos donde ensayar.
- **Creativity:** búsqueda inversa desde Marte hacia la Tierra, con resultado que no elegimos nosotros.
- **Validity:** variables a la misma escala, validación con análogos conocidos, limitaciones escritas.
- **Relevance:** caracteriza, explica dónde se rompe la analogía y conecta con la exploración.
- **Presentation:** un mapa, tres fichas y una historia de una sola idea; dos horas y media reservadas para armarla.

## Queda a criterio de quien lo implemente

Librería del mapa, forma exacta del puntaje, pesos por defecto, y si los resultados se exportan como imagen o como teselas.

## Sin verificar todavía

- Que los archivos de inercia térmica de ASU/PSI estén georreferenciados.
- Dónde se descarga el índice de polvo de TES.
- Cuánta cuota de Earth Engine consume la grilla global.
- Requisitos exactos de entrega de Space Apps 2026, incluida la declaración de uso de IA.
