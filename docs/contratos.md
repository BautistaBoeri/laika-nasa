# Contratos entre las partes

Estos archivos son lo único que une el trabajo de los cuatro. Mientras se respeten, cada uno puede trabajar sin mirar el código de los demás. **Un contrato no se cambia sin avisar en el grupo.**

Los números de los ejemplos son inventados, solo muestran la forma.

## Carpetas y dueños

| Carpeta | Dueño | Qué hay |
|---|---|---|
| `earth/` | Tierra (Nico) | Código de Earth Engine y de similitud |
| `mars/` | Marte | Código que lee los rasters de Marte, y `mars/targets.json` |
| `web/` | Web | La página |
| `web/data/` | Tierra y Contenido | Los datos que la página lee (ver abajo) |
| `content/` | Contenido | Análogos conocidos, textos, presentación |
| `/data/` | nadie (no va a git) | Rasters descargados |

Regla: cada uno edita solo su carpeta. `web/data/` es la excepción: ahí Tierra deja `sites.json` y las imágenes, y Contenido deja `textos.json`.

## 1. Definición de las variables (Tierra y Marte)

Para que la comparación valga, la misma variable se calcula igual en los dos planetas. Propuesta inicial, a confirmar entre Tierra y Marte en la primera media hora:

| id | Qué es | Cómo se calcula | Unidad |
|---|---|---|---|
| `slope` | Pendiente media | Pendiente sobre un modelo de elevación de 463 m por píxel; promedio dentro de la celda de 5 km | grados |
| `roughness` | Relieve local | Desvío estándar de la elevación (píxeles de 463 m) dentro de la celda de 5 km | metros |
| `albedo` | Albedo de onda corta | Promedio dentro de la celda de 5 km | fracción de 0 a 1 |

- **Por qué 463 m:** es la resolución del modelo de elevación de Marte (MOLA). La Tierra tiene datos más finos, y si se calcula la pendiente a 30 m da valores más altos solo por la resolución. Por eso el modelo terrestre se degrada a 463 m antes de calcular.
- **Valor de un sitio de Marte:** media y desvío de cada variable en un círculo de 25 km de radio alrededor del punto.
- **Segunda tanda (después de las 18:00):** `thermal` (comportamiento térmico), `aridity` (aridez), `dust` (polvo). Se definen cuando la primera versión funcione.

## 2. `mars/targets.json` (Marte → Tierra)

```json
{
  "targets": [
    {
      "id": "jezero",
      "name": "Cráter Jezero",
      "lat": 18.44,
      "lon": 77.45,
      "radius_km": 25,
      "values": {
        "slope": { "mean": 3.2, "std": 2.1 },
        "roughness": { "mean": 45.0, "std": 30.0 },
        "albedo": { "mean": 0.15, "std": 0.02 }
      }
    }
  ],
  "mars_global": {
    "slope": { "mean": 2.0, "std": 3.0 },
    "roughness": { "mean": 40.0, "std": 60.0 },
    "albedo": { "mean": 0.2, "std": 0.05 }
  }
}
```

`lon` va en grados este, de -180 a 180. `mars_global` son las estadísticas de todo Marte; sirven para normalizar.

## 3. `content/known_analogs.json` (Contenido → Tierra)

```json
[
  {
    "name": "Desierto de Atacama (Yungay)",
    "lat": -24.1,
    "lon": -70.0,
    "radius_km": 100,
    "body": "mars",
    "source": "https://..."
  }
]
```

`body` es `mars`, `moon` o `both`. `radius_km` es el radio que se va a enmascarar alrededor. `source` es un link que respalde que ese lugar se usa como análogo.

## 4. `web/data/sites.json` (Tierra → Web)

```json
{
  "generated": "2026-11-14T18:00:00-03:00",
  "variables": [
    { "id": "slope", "label": "Pendiente", "unit": "°" },
    { "id": "roughness", "label": "Relieve local", "unit": "m" },
    { "id": "albedo", "label": "Albedo", "unit": "" }
  ],
  "targets": [
    {
      "id": "jezero",
      "name": "Cráter Jezero",
      "lat": 18.44,
      "lon": 77.45,
      "values": { "slope": 3.2, "roughness": 45.0, "albedo": 0.15 },
      "layer": "data/similarity_jezero.png",
      "sites": [
        {
          "id": "-24.1_-66.9",
          "lat": -24.1,
          "lon": -66.9,
          "known": false,
          "score": 0.82,
          "variables": {
            "slope": { "score": 0.84, "earth": 3.9 },
            "roughness": { "score": 0.71, "earth": 61.0 },
            "albedo": { "score": 0.91, "earth": 0.17 }
          },
          "image": "data/img/-24.1_-66.9.jpg"
        }
      ]
    }
  ]
}
```

- Todos los `score` van de 0 a 1. La página los muestra como porcentaje.
- `id` del sitio: latitud y longitud redondeadas a un decimal, unidas con `_`. Así el id no cambia aunque cambie el ranking.
- `known: true` marca un análogo ya conocido (se dibuja en otro color).
- `earth` es el valor medido en la Tierra; el valor de Marte está en `targets[].values`.
- `image` es opcional. Si falta, la página no muestra foto.
- `variables` puede traer más o menos variables según la versión. La página dibuja las que vengan, usando la lista `variables` de arriba para el nombre y la unidad.
- `sample: true` (opcional, en la raíz) marca datos de ejemplo: la página muestra un aviso al pie. Los datos reales no lo llevan.

### Capa de similitud (`layer`)

Un PNG por sitio objetivo, con fondo transparente donde no hay dato.

- Proyección **Web Mercator (EPSG:3857)**, no latitud/longitud plana. Si no, queda corrida respecto del mapa base.
- Límites: longitud de -180 a 180, latitud de -85 a 85.
- Tamaño sugerido: 4096 píxeles de ancho.
- Colores: la misma escala de cinco pasos que usa la página (`--sim-1` a `--sim-5` en `web/styles.css`), con los mismos cortes: rojo `#D94F4F` (< 0,40), `#E8823F` (0,40–0,55), `#D6A13C` (0,55–0,65), `#A9D257` (0,65–0,75), verde `#6EF2AE` (≥ 0,75). Si no, el mapa y la leyenda no coinciden.
- Mientras un sitio objetivo no tenga `layer`, el interruptor de la capa aparece deshabilitado.

## 5. `web/data/textos.json` (Contenido → Web)

```json
{
  "jezero": {
    "region": "Isidis Planitia",
    "blurb": "Antiguo lago con un delta fluvial. Hoy lo explora el rover Perseverance.",
    "mission": "Perseverance · desde 2021"
  },
  "-24.1_-66.9": {
    "name": "Salar de ejemplo",
    "country": "Argentina"
  },
  "jezero:-24.1_-66.9": {
    "name": "Salar de ejemplo",
    "country": "Argentina",
    "why": "Por qué se parece a Jezero…",
    "breaks": "Dónde se rompe la analogía…",
    "use": "Para qué serviría…"
  }
}
```

- Tres tipos de clave en el mismo archivo:
  - **`<sitio de Marte>`** (por ejemplo `jezero`): descripción del sitio marciano para la tarjeta de abajo a la izquierda. Todos los campos son opcionales.
  - **`<sitio de Marte>:<id del sitio>`**: textos de un sitio terrestre comparado con ese sitio de Marte. Es la forma recomendada para `why`, `breaks` y `use`, porque por qué un lugar se parece a Jezero no es lo mismo que por qué se parece a Gale.
  - **`<id del sitio>`**: vale para cualquier sitio de Marte. Sirve para nombre y país. Si existen las dos claves, gana la que incluye el sitio de Marte.
- El `id` del sitio es el de `sites.json`.
- Para los ~15 sitios alcanza con `name` y `country`. `why`, `breaks` y `use` solo para los 3 mejores.
- Si un sitio no está en este archivo, la página muestra las coordenadas en vez del nombre y no muestra texto.
