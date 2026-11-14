# Web

Página estática: HTML, CSS y JavaScript sin paso de compilación. Implementa el diseño del canvas "Laika · Análogos de Marte" en Claude Design.

## Correrla

Tiene que servirse por HTTP; abriendo `index.html` directo el navegador bloquea la lectura de los JSON.

```bash
cd web
python3 -m http.server 8000
```

Y abrir http://localhost:8000.

## Archivos

| Archivo | Qué es |
|---|---|
| `index.html` | Estructura y textos fijos de las secciones |
| `styles.css` | Variables de diseño (colores, escala de similitud, tipografía) y estilos |
| `app.js` | Mapa, puntos, panel de detalle. Los textos de la interfaz están juntos en el objeto `T` |
| `data/sites.json` | Sitios y puntajes. Lo escribe `earth/` (formato en `docs/contratos.md`) |
| `data/textos.json` | Nombres y textos. Lo escribe Contenido |
| `data/land-50m.json` | Contorno de los continentes (Natural Earth, dominio público, vía `world-atlas@2.0.2`) |
| `vendor/` | Leaflet 1.9.4 y topojson-client 3.1.0, copiados para que la demo no dependa de internet |

Los `sites.json` y `textos.json` actuales son **datos de ejemplo** sacados del prototipo de diseño (`"sample": true`), así que la página muestra un aviso al pie. Cuando `earth/` exporte los reales, se reemplazan los archivos y no hay que tocar código.

Sin internet, solo cambia la tipografía (IBM Plex viene de Google Fonts y cae a la del sistema).

## Enlaces directos

La URL guarda el estado: `#sitio=gale&punto=-21.3_118.8` abre Gale con ese sitio seleccionado. Sirve para preparar la demo.
