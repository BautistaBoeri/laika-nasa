# Prompt para Claude Design: la página del proyecto

Pegá todo lo que está debajo de la línea.

---

Quiero que diseñes y prototipes una página web interactiva de una sola pantalla. Es la cara visible de nuestro proyecto para el hackathon NASA Space Apps 2026, y la van a ver jurados en un proyector durante una demo de pocos minutos. Tiene que entenderse en diez segundos, verse cuidada y dar ganas de tocarla.

## Qué es el proyecto

Los científicos prueban instrumentos y entrenan misiones en lugares de la Tierra que se parecen a Marte, llamados análogos. Hoy esos lugares se eligen por tradición y por parecido "a ojo". Nosotros hacemos lo inverso: medimos un sitio real de Marte (por ejemplo el cráter Jezero, donde está el rover Perseverance) con variables numéricas, y buscamos en todo el planeta Tierra qué lugares se le parecen, variable por variable. La página muestra el resultado de esa búsqueda.

El mensaje que tiene que transmitir es: *no elegimos estos lugares, los encontraron los datos*.

Nombre provisorio del proyecto: **Laika**.

## Qué tiene la pantalla

**1. Un mapa del mundo que ocupa casi toda la pantalla.**
Sobre el mapa hay unos 15 puntos: los lugares de la Tierra más parecidos al sitio marciano elegido. El color de cada punto indica qué tan parecido es. Hay además algunos puntos de otro tipo, los análogos ya conocidos (Atacama, Islandia y otros), que tienen que distinguirse a simple vista: están para mostrar que el método también los encuentra solo.

**2. Un selector de sitio de Marte.**
Tres opciones: cráter Jezero, cráter Gale y Arcadia Planitia. Al cambiar, cambian los puntos. Es el control principal y conviene que se note que se está eligiendo un lugar *de Marte*: puede llevar una miniatura o una ficha breve del sitio.

**3. Un interruptor para una capa de similitud.**
Al prenderla, todo el mapa se tiñe según qué tan parecida es cada zona al sitio marciano, con la misma escala de color que los puntos. Necesita una leyenda.

**4. Un panel de detalle que aparece al tocar un punto.**
Es la parte más importante. Muestra:

- nombre del lugar y país;
- puntaje total de similitud, como porcentaje grande;
- una imagen satelital del lugar;
- una barra por variable, cada una con su porcentaje y, al lado, el valor medido en la Tierra y el medido en Marte (por ejemplo "Pendiente · 84 % · 3,9° en la Tierra, 3,2° en Marte");
- tres textos cortos: **Por qué se parece**, **Dónde se rompe la analogía** y **Para qué serviría**.

"Dónde se rompe la analogía" tiene que tener el mismo peso visual que "Por qué se parece". Reconocer los límites es parte de lo que evalúa el jurado; no lo escondas en letra chica.

**5. Dos secciones breves fuera del mapa**, accesibles sin tapar lo principal:

- **Cómo funciona:** el método en tres o cuatro pasos con íconos o un diagrama simple.
- **Límites:** lo que la Tierra no puede reproducir de Marte: la gravedad (38 % de la terrestre), la presión atmosférica (menos del 1 %), la composición del aire y la radiación.

## Estados que el diseño tiene que resolver

- **Sin ningún punto seleccionado:** qué se ve al entrar, y cómo se invita a tocar un punto.
- **Punto seleccionado:** el panel abierto y el punto resaltado en el mapa.
- **Sitio sin texto ni imagen:** la mayoría de los puntos solo tiene números. El panel tiene que verse completo igual, mostrando las coordenadas en lugar del nombre.
- **Análogo conocido seleccionado:** el panel aclara que es un sitio ya estudiado y que sirve de validación.
- **Cantidad variable de barras:** hoy son tres variables (pendiente, relieve local, albedo); más adelante pueden ser seis (se suman comportamiento térmico, aridez y polvo).
- **Capa de similitud prendida y apagada.**

## Dirección visual

- Tema oscuro, pensando en el proyector y en que los puntos resalten.
- Sobrio y científico, más cercano a una herramienta de una agencia espacial que a un póster de ciencia ficción. Sin estrellas animadas, neones ni tipografías futuristas.
- Un guiño a Marte en el color de acento está bien, sin teñir todo de rojo.
- Tipografía legible a distancia; los números de las barras tienen que poder leerse desde el fondo de una sala.
- La escala de similitud, de bajo a alto, en cinco pasos, distinguible para personas con daltonismo y sobre fondo oscuro. Es el elemento visual central: la usan los puntos, las barras y la capa del mapa.
- El color de los análogos conocidos no tiene que confundirse con ningún paso de esa escala.
- Transiciones cortas al abrir el panel y al cambiar de sitio marciano; nada que demore la demo.
- Tiene que funcionar también en un celular: ahí el panel puede subir desde abajo.

## Datos de ejemplo

La página real va a leer un archivo con esta forma. Usala para el prototipo e inventá unos 15 sitios repartidos por los desiertos y zonas áridas del mundo, con tres o cuatro marcados como conocidos. Los valores son de relleno.

```json
{
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
          }
        }
      ]
    }
  ]
}
```

Los puntajes van de 0 a 1 y se muestran como porcentaje. El nombre, el país y los tres textos de cada sitio vienen aparte y pueden faltar.

## Restricciones técnicas

La versión final va a ser una página estática publicada en GitHub Pages, sin servidor: HTML, CSS y JavaScript, con el mapa hecho en Leaflet. Diseñá con eso en mente:

- nada que requiera un backend o un paso de compilación;
- el mapa base tiene que ser uno real y de uso libre, en tono oscuro o satelital;
- los textos de la interfaz en español, y juntos en un solo lugar para poder traducirlos al inglés.

## Qué necesito que entregues

1. El prototipo interactivo de la pantalla, con los estados de arriba.
2. Los valores de diseño como variables CSS: colores, la escala de similitud de cinco pasos, el color de los análogos conocidos, tipografías, espaciados y radios. Los vamos a reutilizar en la presentación y para pintar la capa del mapa.
3. Una nota corta con las decisiones que tomaste y cualquier duda que te haya quedado.
