# Rol: Web

Leé primero [el diseño](../diseno.md) y [los contratos](../contratos.md).

## Qué te toca

La página que ve el jurado: un mapa del mundo con los sitios análogos como puntos, y una vista de detalle al tocar cada uno. Tiene que ser dinámica, sencilla y visualmente llamativa. Es lo que más pesa en Presentation.

- **Tu carpeta:** `web/` (menos `web/data/`, donde otros dejan los datos)
- **Recibís:** `web/data/sites.json` y la capa PNG (de Nico, a las 18:00), `web/data/textos.json` (de Contenido)
- **Entregás:** la página publicada en una URL

No dependés de nadie hasta las 18:00: arrancá con datos de mentira.

## Qué tiene la página

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
│  Pendiente    ████████░░  84%   3,9° vs 3,2°  │
│  Relieve      ███████░░░  71%   61 m vs 45 m  │
│  Albedo       █████████░  91%   0,17 vs 0,15  │
│  Por qué se parece · Dónde se rompe ·         │
│  Para qué serviría                            │
└───────────────────────────────────────────────┘
```

1. **Mapa del mundo** con unos 15 puntos por sitio objetivo. Color o tamaño según el puntaje.
2. **Selector de sitio de Marte** (Jezero, Gale, Arcadia): cambia los puntos y la capa.
3. **Análogos conocidos** (`known: true`) en otro color, con leyenda. Muestran que el método funciona.
4. **Capa de similitud** que se prende y apaga: un PNG semitransparente sobre el mapa.
5. **Vista de detalle** al tocar un punto:
   - nombre y país (de `textos.json`; si no está, las coordenadas);
   - puntaje total;
   - una barra por variable, con el valor de la Tierra al lado del de Marte;
   - imagen, si viene;
   - los tres textos, si vienen: por qué se parece, dónde se rompe la analogía, para qué serviría.
6. **Sección corta "Cómo funciona"** y **"Límites"**: de dónde salen los datos y qué no puede reproducir la Tierra. El texto lo escribe Contenido.

## Reglas que salen de los contratos

- La página **dibuja las variables que vengan** en el JSON, no una lista fija. Hoy son tres; a la noche van a ser más.
- Si un sitio no tiene texto o imagen, se muestra igual, sin esa parte.
- Los puntajes vienen de 0 a 1 y se muestran como porcentaje.
- La capa PNG viene en **Web Mercator**, de -180 a 180 de longitud y de -85 a 85 de latitud.

## Decisiones tuyas

- **Librería de mapa.** Opciones: Leaflet (la más simple) o MapLibre GL (permite vista de globo, más llamativa). Elegí la que te deje tener algo andando en dos horas.
- **Con o sin framework.** No hay backend: es una página estática que lee dos JSON. HTML con JavaScript alcanza; React también vale si te resulta más rápido.
- **Mapa base.** Conviene uno oscuro o satelital, para que los puntos resalten. Revisar la licencia del que elijas y poner la atribución. NASA GIBS ofrece capas satelitales abiertas y suma para el jurado.
- **Publicación.** El repo está en GitHub (`BautistaBoeri/laika-nasa`): GitHub Pages es lo más directo.

## Pasos

1. **Crear `web/data/sites.json` de mentira** copiando el ejemplo de los contratos y agregando 10 o 15 sitios inventados repartidos por el mundo, algunos con `known: true`.
2. **Mapa con puntos** leyendo ese JSON.
3. **Vista de detalle** con las barras.
4. **Publicar** aunque esté incompleta, para tener la URL andando temprano.
5. **Selector de sitio objetivo y capa de similitud.**
6. **18:00: enchufar los datos reales** de Nico.
7. **Pulir:** transiciones, vista en celular, textos de "Cómo funciona" y "Límites".

## Horarios

| Cuándo | Qué |
|---|---|
| 14:00 | Mapa con puntos de mentira y detalle básico |
| 16:00 | Publicada en una URL |
| 18:00 | Datos reales de Jezero integrados |
| 23:00 | Selector de sitios, capa, análogos conocidos, textos |
| Dom 11:00 | Pulida y congelada; después solo arreglos |

## Cuidados

- Probar la página **desde la URL pública**, no solo en local: las rutas a `data/` suelen romperse al publicar.
- En la demo va a haber un proyector y mala conexión: que cargue rápido y se lea de lejos.
- Las barras necesitan texto con el número, no solo color, para que se entiendan en una captura.

## Para arrancar con tu Claude

> Tengo el rol Web en este proyecto. Leé `docs/diseno.md`, `docs/contratos.md` y `docs/roles/web.md`. Trabajá solo dentro de `web/`. Empecemos por crear un `web/data/sites.json` de mentira según el contrato y un mapa que muestre esos puntos.
