# Dirección de diseño

Qué decisiones visuales tiene la página y por qué. Los valores exactos están en las variables de `styles.css`; acá va el motivo de cada una.

## Identidad

Una herramienta de consulta, sobria, más cerca de un visor de una agencia espacial que de un póster de ciencia ficción. Sin estrellas animadas, neones ni tipografías futuristas. El mapa es el contenido: todo lo demás se corre para dejarlo ver.

## Tema

Un solo tema, oscuro. Dos motivos: la página se muestra en un proyector, donde un fondo claro encandila, y los puntos del mapa necesitan un fondo oscuro para que la escala de similitud, que termina en blanco, se lea.

## Color

Cada color tiene un solo rol.

| Color | Variables | Rol |
|---|---|---|
| Azules oscuros | `--page`, `--bg`, `--surface*`, `--land`, `--line` | Fondo, océano, tierra, tarjetas y bordes. No llevan dato. |
| Rojo oscuro a blanco | `--sim-1` a `--sim-5` | Similitud con el sitio de Marte, y nada más. Cuanto más blanco, más parecido. Es un solo tono con pasos parejos de luminosidad, para que el orden se lea también con daltonismo. |
| Celeste | `--known` | Análogos que ya se usaban antes de este trabajo. Va siempre con forma de rombo, así no depende solo del color. |
| Azul vivo | `--accent`, `--accent-text` | Controles: desplegable, interruptor encendido, foco del teclado. |
| Azul medio | `--line-strong` | Borde de los controles. Da un contraste de 3:1 o más contra el fondo. |

El naranja y el rojo no se usan como adorno ni como acento de la interfaz: si algo es naranja, es un puntaje de similitud. La única excepción es el dibujo del globo de Marte en la tarjeta del sitio.

Los cortes de la escala (40, 55, 65 y 75 %) son los mismos en la página y en la capa que exporta `earth/`. Si cambian en un lado, cambian en el otro.

## Tipografía

- **IBM Plex Sans** para todo el texto. Se lee bien a distancia y tiene pesos suficientes para marcar jerarquía sin recurrir a mayúsculas.
- **IBM Plex Mono** para cifras: puntajes, valores medidos y coordenadas. Todos los dígitos ocupan el mismo ancho, así los números quedan alineados y se comparan de un vistazo.

Las dos están copiadas en `vendor/fonts/`, para que la página no dependa de internet durante la demo. Lo único que necesita conexión es la vista satelital.

Los títulos y las etiquetas van en mayúscula inicial. No se usan etiquetas en mayúsculas con letras separadas.

## Composición

- La primera pantalla es el mapa completo. La tarjeta del sitio de Marte y la leyenda van en las esquinas de abajo para no tapar los puntos.
- Las cifras del sitio de Marte van en tarjetas, porque son datos sueltos que se leen por separado.
- No hay íconos decorativos. Los símbolos que quedan significan algo: el rombo es un análogo conocido, el "+" y el "−" marcan en qué se parece un sitio y en qué no.

## Accesibilidad

- Todo control mide al menos 44 px de alto y de ancho.
- Todo se puede usar con teclado y el foco siempre se ve.
- Si el sistema pide menos movimiento, la página y el mapa dejan de animar.
