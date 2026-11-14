# Rol: Contenido

Leé primero [el diseño](../diseno.md) y [los contratos](../contratos.md).

## Qué te toca

Todo lo que convierte un mapa con puntos en un proyecto que convence: la lista de análogos ya conocidos, los textos de los sitios, las limitaciones, la presentación y la entrega oficial. La guía de Space Apps avisa que los equipos suelen descuidar la presentación, y es uno de los cinco criterios.

- **Tu carpeta:** `content/`, más el archivo `web/data/textos.json`
- **Recibís:** los resultados de Nico (los 15 sitios) a partir de las 18:00
- **Entregás:** `content/known_analogs.json` (13:00), `web/data/textos.json`, la presentación, el video y la página del proyecto en Space Apps

## Tareas, en orden

### 1. Análogos conocidos (antes de las 13:00)

Es lo único que frena a otro: Nico lo necesita para validar el método.

Armar `content/known_analogs.json` (formato en los contratos) con unos 15 a 20 lugares que ya se usan como análogos de Marte, cada uno con coordenadas, un radio y un link que lo respalde. Para empezar:

- Desierto de Atacama (Chile)
- Valles Secos de McMurdo (Antártida)
- Islandia (campos de lava)
- Mauna Kea / Mauna Loa (Hawái, sede de HI-SEAS)
- Cráter Haughton, isla Devon (Canadá)
- Death Valley y desierto de Mojave (EE. UU.)
- Desierto de Utah (sede de MDRS)
- Río Tinto (España)
- Svalbard (Noruega)
- Depresión de Danakil / Dallol (Etiopía)
- Cuenca de Qaidam (China)
- Wadi Rum (Jordania)
- Pilbara (Australia)
- Desierto del Néguev (Israel)
- Puna argentina / altiplano

Buscar las coordenadas y la fuente de cada uno; no confiar en la memoria.

### 2. Reglas de entrega (antes de las 15:00)

El sitio de Space Apps bloquea la lectura automática, así que hay que leerlo a mano. Averiguar y anotar en `content/entrega.md`:

- qué pide la página del proyecto (resumen, descripción, links);
- formato y duración de la demo (video o diapositivas);
- **cómo se declara el uso de inteligencia artificial**, porque estamos usando Claude;
- hora límite exacta y si hay presentación en vivo en Buenos Aires.

### 3. Texto general de la página (antes de las 18:00)

Dos bloques cortos para Web:

- **Cómo funciona:** el método en cuatro frases, con las fuentes de datos.
- **Límites:** lo que la Tierra no puede reproducir. Datos para arrancar, a verificar con fuente:
  - gravedad de Marte: 38 % de la terrestre;
  - presión en superficie: menos del 1 % de la terrestre;
  - atmósfera: 95 % dióxido de carbono;
  - temperatura media: alrededor de -60 °C;
  - sin campo magnético global, así que mucha más radiación en superficie.

### 4. Nombres y textos de los sitios (desde las 18:00)

Cuando Nico entregue los 15 sitios:

- Ponerle **nombre y país** a cada uno, mirando las coordenadas en un mapa.
- **Descartar o marcar** los que resulten ser análogos ya estudiados que no estaban en la lista.
- Para los **3 mejores**, escribir en `web/data/textos.json`:
  - **Por qué se parece:** apoyado en los números de las barras, no en "se ve parecido".
  - **Dónde se rompe:** qué variables dan mal y qué no se puede reproducir.
  - **Para qué serviría:** probar movilidad de rovers, ensayar instrumentos, entrenar operaciones, buscar recursos. Incluir acceso: qué tan lejos está de una ruta o ciudad.
- Buscar si ya existe literatura sobre esos 3 lugares como análogos. Si no hay, es el dato más fuerte para Creativity; si hay, se dice.

### 5. Presentación (domingo de 8:00 a 13:30)

Una sola idea: *no elegimos el lugar, le preguntamos a los datos*. Estructura sugerida:

1. El problema: los análogos se eligen por tradición y se parecen "a ojo".
2. La idea: partir de Marte y buscar en toda la Tierra.
3. Cómo funciona, en una imagen.
4. La prueba: el método encuentra solo los análogos conocidos.
5. El hallazgo: los 3 sitios nuevos, con demo en vivo.
6. Dónde se rompe la analogía y qué no sabemos.
7. Para qué sirve y qué sigue.

Revisar que cada criterio (Impact, Creativity, Validity, Relevance, Presentation) tenga al menos una diapositiva que lo responda.

### 6. Entrega (domingo de 13:30 a 14:30)

Página del proyecto, link a la web, link al repo, video, lista de datos y fuentes, y declaración de uso de IA. Subir todo a las 14:30, no a las 14:59.

## Horarios

| Cuándo | Qué |
|---|---|
| 13:00 | `known_analogs.json` |
| 15:00 | Reglas de entrega anotadas |
| 18:00 | Textos "Cómo funciona" y "Límites" |
| 23:00 | Nombres de los 15 sitios; borrador de los 3 textos |
| Dom 11:00 | Textos finales; esqueleto de la presentación |
| Dom 13:30 | Presentación y video listos |
| Dom 14:30 | Todo enviado |

## Cuidados

- Todo dato que se afirme lleva fuente. Llevar la lista de referencias desde el principio en `content/referencias.md`.
- Los resultados pueden cambiar hasta el domingo a las 11:00: no pulir los textos de los 3 sitios antes de que se congele el análisis.
- Si el método no encuentra los análogos conocidos, también se cuenta. Reconocer límites suma en Validity.

## Para arrancar con tu Claude

> Tengo el rol Contenido en este proyecto. Leé `docs/diseno.md`, `docs/contratos.md` y `docs/roles/contenido.md`. Trabajá solo dentro de `content/` y en `web/data/textos.json`. Empecemos por armar `content/known_analogs.json` con coordenadas y fuentes verificadas.
