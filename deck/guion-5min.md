# SPHEREx Time Machine — guion de 5 minutos

Nueve diapositivas. Ritmo: unas 140 palabras por minuto. No corras: los silencios entre diapositivas
cuentan y hacen que suene seguro. Si vas tarde, el recorte está marcado al final.

| Tramo | Diapositiva | Dura | Acumulado |
|---|---|---|---|
| 1 | Portada | 0:40 | 0:40 |
| 2 | **DEMO EN VIVO** | 1:05 | 1:45 |
| 3 | Paso 1 | 0:20 | 2:05 |
| 4 | Paso 2 | 0:25 | 2:30 |
| 5 | Paso 3 | 0:25 | 2:55 |
| 6 | Paso 4 | 0:25 | 3:20 |
| 7 | Paso 5 | 0:30 | 3:50 |
| 8 | Paso 6 | 0:40 | 4:30 |
| 9 | Cierre | 0:30 | **5:00** |

---

## 1 · Portada — 0:40

> SPHEREx es un telescopio de la NASA que fotografía **el cielo entero** cada seis
> meses. No una zona: entero. Y lo hace en 102 colores de infrarrojo a la vez.
>
> Eso quiere decir que de cualquier punto del cielo existen decenas de fotos
> tomadas en fechas distintas. Si algo se movió, está ahí dentro. El problema es
> que viven en un archivo científico que nadie de fuera abre.
>
> Esto es SPHEREx Time Machine. Eliges un trozo de cielo, le das a play, y ves
> pasar quince meses de fotos reales de la NASA.

**Haz esto:** no leas los cuatro números de la portada. Se leen solos.

---

## 2 · DEMO EN VIVO — 1:05

Cambia a la herramienta. Ten **Vesta ya cargado** antes de empezar a hablar.

> Esto es Vesta, un asteroide del cinturón principal.

*(dale a play, calla dos segundos, deja que lo vean)*

> Todo el fondo se queda quieto y una cosa cruza. Eso es un objeto del sistema
> solar moviéndose de verdad. No es una animación: son ocho fotos distintas.

*(click en "Difference")*

> Y si resto dos fechas, todo lo que no cambió se va a negro. Solo queda lo que
> se movió.

*(click en una estrella del encuadre)*

> Y esto es lo que más me gusta. Como cada visita midió un color distinto,
> pinchar una estrella te da su espectro. Treinta visitas, treinta puntos.

*(vuelve a las diapositivas)*

> Hay 37 sitios dentro y 1073 fotos. Os cuento en seis pasos cómo llegó todo eso
> a caber en una página web.

**Haz esto:** la demo va desde un archivo local, sin internet. Si la sala tiene
wifi malo, da igual. Ensáyala tres veces hasta que salga sin pensar.

---

## 3 · Paso 1 — 0:20

> Lo primero era preguntarle al archivo de la NASA qué tenía. Hay un millón y
> medio de fotos ahí esperando. Se consulta en ADQL, que se parece a SQL.

---

## 4 · Paso 2 — 0:25

> Cada foto pesa 71 megas, y yo solo quería un cuadradito. Así que en vez de
> bajarla entera, pedí exactamente los bytes de esa zona: 1,3 megas.
>
> Como arrancar una página en vez de cargar con el libro.

---

## 5 · Paso 3 — 0:25

> El telescopio vuelve al mismo sitio, sí, pero **girado**. Si no lo corriges, al
> pasar las fotos las estrellas bailan y no hay forma de saber qué se movió de
> verdad.
>
> Las enderecé todas. Cero píxeles de desfase entre dos épocas.

---

## 6 · Paso 4 — 0:25

> SPHEREx no tiene filtros de colores. El color que capta depende de dónde caiga
> la estrella en el sensor.
>
> Yo leía esa tabla en una posición fija, y resulta que cambia de tamaño según el
> detector. Me daba 0,05 micras donde debía haber 2. Por ahí descubrí el fallo.

**Haz esto:** cuenta el error con naturalidad. Un error encontrado y arreglado
convence más que un proyecto que parece salido perfecto.

---

## 7 · Paso 5 — 0:30

> ¿Y cómo sé que no me lo he inventado? Cogí una estrella y medí su brillo en las
> treinta visitas. Las tomadas en el mismo color, aunque estén separadas medio
> año, dan el mismo número. Un uno por ciento de diferencia.
>
> Eso solo cuadra si el enderezado, la tabla de colores y la medida del brillo
> están bien **a la vez**.

---

## 8 · Paso 6 — 0:40

> Y esto es lo que buscaba desde el principio.
>
> Le pregunté a JPL dónde estaban Vesta, Neptuno y Urano en el instante exacto de
> cada foto. Luego fui a mirar si había algo en esas coordenadas.
>
> Lo había. 65 de 68 veces.
>
> Las posiciones no están ajustadas a los píxeles: vienen de fuera. Que el
> círculo caiga encima de una fuente es una comprobación de verdad. Y en puntos
> de control, donde no debería haber nada, el resultado se desploma.
>
> Los tres fallos son las longitudes de onda más largas, donde la luz zodiacal
> ahoga a Neptuno.

---

## 9 · Cierre — 0:30

> Mil setenta y tres fotos, ninguna inventada. Nada está apilado ni reescalado:
> cada imagen lleva el brillo que midió la NASA.
>
> Funciona sin internet y se puede instalar como aplicación.
>
> El reto pedía que cualquiera pudiera ver cómo cambia el cielo. Creo que lo más
> parecido a conseguirlo es que alguien le dé a play y lo vea sin que nadie se lo
> explique.
>
> Gracias.

---

## Si vas tarde

Recorta en este orden:

1. **Paso 1 entero** (–20 s). Se entiende sin él.
2. La segunda mitad del **Paso 6**, de "Las posiciones no están ajustadas" en
   adelante (–20 s). Guárdalo para las preguntas.
3. El espectro de la **demo** (–15 s). Es lo bonito, así que quítalo el último.

Nunca recortes la demo entera ni el Paso 5. Son los dos que demuestran que esto
es real.

## Munición para las preguntas

- **¿Por qué no pide los datos en directo?** El servidor de IRSA no manda la
  cabecera CORS, así que el navegador rechaza la respuesta. Todo el trabajo
  pesado se hace antes; la página solo pinta.
- **¿Detecta cosas automáticamente?** Lo intenté tres veces y lo borré. Encontraba
  unos ocho objetos por foto y casi todos eran rayos cósmicos. Como cada visita
  mide un color distinto, una estrella puede desaparecer por física normal, no
  por haberse movido. Preferí no enseñar basura.
- **¿Cuánto pesa?** 46 MB de recortes para los 37 sitios.
- **¿De dónde salen los sitios?** 13 clásicos elegidos a mano y 24 encontrados
  automáticamente, con el filtro de 120 visitas mínimo y 60 días de separación.
- **¿Qué harías con más tiempo?** Un detector de movimiento que compare solo
  visitas de la misma banda, que es donde fallaba el mío.
