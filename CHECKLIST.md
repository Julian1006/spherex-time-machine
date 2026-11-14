# Checklist del reto (NASA Space Apps)

Leyenda: ✅ ya está · ⚠️ a medias · ❌ falta

> Estado al 14 de noviembre de 2026. La búsqueda por coordenadas y el robot diario ya están publicados. Lo marcado con 🆕 funciona en la copia del proyecto que está en el computador y **falta subirlo a GitHub**.

## Lo que pide el reto

- [x] ✅ **Herramienta web pública.** Está publicada en GitHub Pages.
- [x] ✅ **Muestra imágenes reales de SPHEREx.** Son imágenes Level-2 del archivo de IRSA.
- [x] ✅ **Reproduce las imágenes como un video.** Tiene play, pausa, cuadro por cuadro, velocidad y línea de tiempo.
- [x] ✅ **Facilita ver objetos que se mueven.** Tiene los modos Blink y Difference, un marcador que sigue a las estrellas que se mueven y 🆕 zoom hasta 8× para que un corrimiento de 1 o 2 píxeles se note.
- [x] ✅ **Facilita ver objetos que cambian de brillo.** 🆕 La gráfica de brillo ahora también se puede ver "por fecha", con una línea por cámara.
- [x] ✅ **El usuario escribe RA y Dec.** En "Go to any coordinates", debajo de los lugares guardados.
  - [x] Un campo para RA y otro para Dec.
  - [x] Acepta `08h55m10.831s`, `08:55:10.8`, `8 55 10.8`, `133.795`, `-7d14m42.53s`, `−7° 14′ 42.5″`, `-7.245` y más. Probado con 24 formas distintas.
  - [x] Si algo está mal escrito o fuera de rango, lo dice con un mensaje claro y no carga nada.
  - [x] También se puede buscar por nombre ("Proxima Centauri", "M51"). Pregunta al catálogo público SIMBAD.
- [x] ✅ **Trae imágenes de cualquier punto del cielo, en vivo.**
  - [x] El navegador lee las imágenes directo de la bodega pública de la NASA.
  - [x] Un cuaderno de apuntados dice qué imágenes cubren cada punto.
  - [x] Muestra el avance mientras carga, y un mensaje si no hay imágenes.
- [x] ✅ **Fácil de usar.** La página abre con una portada de fotos reales y los 37 lugares guardados. Las coordenadas están en una pestaña aparte para quien las necesite.

## Cómo funciona la búsqueda por coordenadas

1. **Escribes las coordenadas** (o un nombre, o tocas uno de los cinco botones de ejemplo).
2. **La página mira el cuaderno de apuntados.** Es una lista de hacia dónde miró el telescopio en cada exposición. Con eso sabe qué fotos muestran ese lugar. Tarda menos de un segundo.
3. **Pide las fotos a la NASA.** De cada una baja solo la tirita donde está el lugar: cerca de 1 MB en vez de 65 MB.
4. **Las endereza** con el norte arriba y **arma el video** en el mismo visor de siempre.

Nada pasa por un servidor nuestro. Los 37 lugares guardados siguen viniendo dentro de la página, para que abra al instante y funcione sin internet.

### El cuaderno de apuntados (la base de datos)

- **De dónde sale.** `build/pointing_index.py` recorre la bodega de la NASA, ve qué fotos existen y lee 11 KB de una foto por exposición. No depende del catálogo de IRSA, que resultó lento y a ratos no responde.
- **Por qué es pequeño.** Las seis cámaras del telescopio están siempre en la misma posición entre sí, como seis ventanas de un bus. Basta anotar hacia dónde miraba el telescopio, y la página calcula qué veía cada cámara.
- **Dónde queda.** En `docs/idx/`: un archivo por cada media semana de observaciones y un archivo `manifest.json` con el resumen.
- **Cómo crece.** Un robot (`.github/workflows/pointing-index.yml`) revisa la bodega todos los días y anota lo nuevo. Los domingos lo lee todo otra vez.
- **Siempre la versión más reciente.** Si la misma semana existe en dos versiones de datos, gana la más nueva (una versión definitiva "dr" le gana a una rápida "qr", y un número mayor a uno menor). El día que la NASA suba una versión nueva, el robot cambia solo.

### Lo que se puede poner en el enlace

| Parámetro | Para qué sirve |
|---|---|
| `ra`, `dec` | El lugar, en cualquier forma que acepten las casillas: `?ra=08h55m10.831s&dec=-7d14m42.53s` |
| `name` | Un nombre. Si va solo, sin `ra` ni `dec`, la página lo busca en SIMBAD |
| `fov` | Tamaño del cuadro en minutos de arco, de 3 a 60. Normal: 13 |
| `n` | Cuántas imágenes, de 2 a 90. Normal: 30 |
| `band` | Del 1 al 6, para quedarse con una sola cámara |
| `when=new` | Solo las imágenes más nuevas |
| `pmra`, `pmdec` | Movimiento propio de la estrella, para que el marcador la siga |
| `embed=1` | Muestra solo el visor, para ponerlo dentro de otra página |
| `lang` | `es` o `en`, para fijar el idioma |

## Lo nuevo del visor 🆕

- **Zoom y arrastre.** Botones `+` y `−` sobre la imagen, las teclas `+ − 0`, pellizco con dos dedos, o Ctrl y la rueda del ratón. Arrastrando se mueve la imagen. Llega hasta 8×.
- **Guardar la imagen.** Baja un PNG de lo que se ve, con la fecha, el color, la barra de escala y el nombre del lugar.
- **Sumar imágenes.** En "Compare" → "Add images together": una foto por cámara (suma todas las fechas) o por cámara y temporada (para poder comparar una temporada con otra). Con "Keep it centred" la suma sigue al objeto que se mueve.
- **Marcar estrellas conocidas.** Catálogos Gaia (círculos) y WISE (cuadros). Las de Gaia se corren a donde deben estar en la fecha de cada foto.
- **Pintar los píxeles con aviso.** Lee de cada archivo de la NASA la capa de avisos y la pinta en cinco colores: píxel dañado, demasiado brillante, raya (satélite), fantasma de una estrella brillante y golpe de rayo cósmico.
- **Brillo por fecha.** La gráfica de abajo cambia entre "por color" (espectro) y "por fecha" (curva de brillo).
- **Ver el mismo lugar en Aladin.** Un botón abre el atlas público Aladin en ese punto del cielo.
- **Dos idiomas.** Inglés y español. La página abre en el idioma del navegador; el botón de arriba a la derecha lo cambia, y `?lang=es` en el enlace lo deja fijo. Son 398 frases traducidas, y el programa que arma la página avisa si alguna queda sin traducir.
- **Portada y título.** La página abre con una pared de 16 fotos reales que van cambiando de fecha; arriba de la imagen sale el nombre de lo que se está mirando.

## Pruebas hechas

| Prueba | Resultado |
|---|---|
| 6 imágenes guardadas, leídas otra vez en vivo y comparadas punto por punto | Entre 99,99 % y 100 % de los píxeles idénticos |
| Una foto de Orión en vivo contra la misma foto guardada | Coinciden en 99,98 %. Volteadas coinciden solo en 45-55 %, así que la orientación es la correcta |
| Posición que predice el cuaderno contra la posición real en el archivo | Menos de 0,3 píxeles de diferencia en los 50 archivos revisados |
| Cantidad de fotos en el cuaderno contra la cantidad que tiene el catálogo de IRSA | Iguales: 1.628.230 |
| Las fotos que encuentra el cuaderno contra las que da el catálogo de IRSA, en los cinco objetos del reto | De 3.909 solo deja fuera 31, todas a menos de 5 píxeles del borde de la cámara. Se dejan fuera a propósito |
| El "mapa rápido" del cuaderno, a fuerza bruta en 68 puntos del cielo | No escondió ninguna de las 1.667 coincidencias reales |
| El marcador de la estrella de Barnard contra la estrella misma, en 30 fotos | Quedan a 2,2″ de distancia (un tercio de píxel de la cámara), y la estrella sube hacia el norte como debe |
| Imagen alejada (26′) contra la normal promediada de a 2×2 | Iguales hasta el séptimo decimal |
| 24 formas de escribir coordenadas | Todas bien leídas |
| Cancelar una carga para abrir un lugar guardado | El lugar guardado no se pisa y los botones vuelven a servir |
| 🆕 Avisos por píxel: contar los píxeles de cada aviso en un archivo entero y comparar con la cuenta que trae el mismo archivo | Iguales en los 21 avisos de un archivo comprimido (DR1) y en los 16 de uno sin comprimir (QR2) |
| 🆕 Los avisos caen en el sitio correcto | El centro "quemado" de Andrómeda sale como "demasiado brillante" justo encima; una raya de satélite sale marcada de lado a lado en una foto de la estrella de Barnard |
| 🆕 La marca de Gaia para la estrella de Barnard contra el marcador propio de la página, en 3 fechas | El mismo píxel, con tres decimales |
| 🆕 La posición de WISE (año 2010) para la estrella de Barnard | Queda 26 a 28 píxeles atrás de la estrella: son 16 años a 10,4″ por año |
| 🆕 WISE 0855 en una sola foto contra 43 fotos sumadas siguiendo su movimiento | 5 veces el ruido contra 20 veces el ruido, justo debajo del marcador |
| 🆕 Curva de brillo de RW Aurigae, 60 fotos en un año | Se apaga cerca de 45 % en las cámaras 5 y 6 y sube en la cámara 1 |
| 🆕 Página en celular (375 px), tema claro y modo incrustado | Sin desbordes; la portada y el pie se esconden en modo incrustado |
| 🆕 Página en español | Ninguna de las 398 frases quedó en inglés; el botón cambia de idioma y vuelve |

## Objetos de prueba

Cada uno tiene su botón en la pestaña de coordenadas.

| Objeto | Qué es | Fotos disponibles | Fechas | Qué muestra la página |
|---|---|---|---|---|
| Barnard's Star | La estrella que más rápido se mueve en el cielo (10,4″ por año) | 335 | 15 ago 2025 a 22 sep 2026 | 30 fotos en las 6 cámaras. El marcador se mueve 1,9 píxeles y la estrella lo sigue. Con zoom se ve el corrimiento |
| Epsilon Indi B | Par de enanas marrones (4,7″ por año) | 381 | 24 abr 2025 a 2 oct 2026 | 30 fotos. El marcador se mueve 1,1 píxeles |
| WISE 0855-0714 | Enana marrón muy fría y rápida (8,2″ por año) | 238 (43 en la cámara 6) | 5 may 2025 a 14 may 2026 | 🆕 Ya se ve: sumando las 43 fotos de la cámara 6 con "Keep it centred" aparece justo en el marcador |
| RW Aurigae | Estrella joven que cambia de brillo | 308 | 1 sep 2025 a 16 sep 2026 | 🆕 La curva "por fecha" muestra el cambio de un año |
| R Draconis | Estrella que late cada 245 días | 2.189 | 24 abr 2025 a 24 sep 2026 | 60 fotos en 17 meses. Es tan brillante que quema el centro, y la página mide su resplandor de alrededor (medida gruesa) |

Cada carga de 30 fotos tardó entre 9 y 10 segundos y pesó entre 36 y 45 MB. "Fotos disponibles" cuenta solo las fotos donde el cuadro completo de 13′ cabe dentro de una cámara.

## Problemas resueltos y pendientes

- [x] **Las coordenadas de catálogo son viejas.** Las de WISE 0855 que da el reto son de 2010, y desde entonces se movió unos 2′. Para las estrellas que se mueven rápido la página calcula dónde están hoy y centra ahí la imagen.
- [x] **Las fotos salían de cabeza.** La página dibujaba el norte abajo aunque la etiqueta decía "N ↑". Ya está corregido, también en los 37 lugares guardados.
- [x] **El script de Python ya no encontraba datos nuevos.** Buscaba la versión QR2, que IRSA reemplazó por DR1. `build/resolve.py` ahora reconoce cualquier versión.
- [x] 🆕 **El movimiento es de apenas 1-2 píxeles.** Con el zoom y el tamaño "cerca" (6,6′) ya se nota.
- [x] 🆕 **WISE 0855 es muy débil.** Resuelto sumando las fotos de la cámara 6.
- [x] 🆕 **Curva de luz.** La gráfica "By date".
- [ ] **R Draconis quema el detector.** Su curva de brillo sale con saltos que no son de la estrella. Haría falta un modelo de la mancha de luz del telescopio para medirla bien.
- [ ] **Aladin dentro de la página.** Hoy es un botón que lo abre en otra pestaña; el servidor de Aladin no respondió el día de la prueba, así que no se pudo ensayar incrustado.

## Consideraciones del reto

| # | Consideración | Estado | Qué falta |
|---|---|---|---|
| 1 | **Fácil de actualizar con datos nuevos** | ✅ El robot diario lo hace solo. Corrió dos veces en GitHub (rápida y completa) y sacó el mismo cuaderno | Ver que guarde cambios el día que la NASA suba fotos nuevas |
| 2a | **Aprovechar las 102 bandas** | ✅ Filtro por cámara, antes y después de cargar, y orden por longitud de onda | — |
| 2b | **Sumar las imágenes de cada una de las 6 cámaras** | ✅ 🆕 "Add images together → one picture per band" | — |
| 2c | **Espectros al momento** | ✅ Clic en una estrella y sale su espectro, también en lugares buscados por coordenadas | — |
| 3 | **Sumar o restar imágenes de fechas distintas** | ✅ 🆕 Sumar por temporada, y restar una temporada de otra con Difference | — |
| 4 | **Que el usuario elija el campo de visión** | ✅ Tres tamaños (6,6′, 13′ y 26′), cualquier valor de 3 a 60 por el enlace, y 🆕 zoom hasta 8× dentro de la imagen | — |
| 5 | **Superponer datos de Gaia o WISE** | ✅ 🆕 Marcas de los dos catálogos encima de la imagen | — |
| 6 | **Coordenadas en el enlace para incrustar** | ✅ `?ra=…&dec=…` y `&embed=1` | — |
| 7 | **Mostrar metadatos como los flags de contaminación** | ✅ 🆕 Avisos de la exposición y, píxel por píxel, los avisos de la NASA pintados encima | — |
| 8 | **Usar herramientas públicas** | ✅ Astropy en el build, SIMBAD para los nombres, 🆕 VizieR para Gaia y WISE, y un botón hacia Aladin | Aladin incrustado en la página (opcional) |

## Extras opcionales

- [x] Buscar por nombre además de por coordenadas.
- [x] 🆕 Descargar la imagen como PNG.
- [x] 🆕 Descargar la animación como video: MP4 en Chrome y Edge, WebM donde el navegador no hace MP4. Probado reproduciéndolo: Vesta cruza la imagen igual que en pantalla.
- [x] 🆕 **Asteroides y cometas conocidos** encima de la imagen, preguntando a SkyBoT (IMCCE) foto por foto. Solo los más brillantes que magnitud 21. En las 8 fotos de Vesta, el rombo de SkyBoT cae a 0,05 píxeles del círculo del JPL.
- [x] 🆕 **¿A qué distancia está?** Se toca algo en dos fotos y la página calcula su distancia por cómo se movió, suponiendo una órbita casi circular alrededor del Sol. Con clics a mano: Neptuno 3 %, Urano 5 %, Vesta 6 % de diferencia con el JPL. Dice también cuánto se movería un Planeta X a 600 UA. Si algo no se mueve (menos de 3 píxeles) o no cuadra con ninguna órbita, lo dice en vez de inventar una distancia.
- [x] 🆕 Titular en la portada: "Dale play al cielo. Lo que se mueve se delata solo."
