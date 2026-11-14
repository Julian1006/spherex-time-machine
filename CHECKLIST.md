# Checklist del reto (NASA Space Apps)

Leyenda: ✅ ya está · ⚠️ a medias · ❌ falta

> Estado al 14 de noviembre de 2026. Todo lo marcado como hecho funciona en la copia del proyecto que está en el computador. **Falta subirlo a GitHub** para que se vea en la página pública.

## Lo que pide el reto

- [x] ✅ **Herramienta web pública.** Está publicada en GitHub Pages.
- [x] ✅ **Muestra imágenes reales de SPHEREx.** Son imágenes Level-2 del archivo de IRSA.
- [x] ✅ **Reproduce las imágenes como un video.** Tiene play, pausa, cuadro por cuadro, velocidad y línea de tiempo.
- [x] ✅ **Facilita ver objetos que se mueven.** Tiene los modos Blink y Difference, y un marcador que sigue a las estrellas que se mueven.
- [x] ✅ **El usuario escribe RA y Dec.** En "Go to any coordinates", debajo de los lugares guardados.
  - [x] Un campo para RA y otro para Dec.
  - [x] Acepta `08h55m10.831s`, `08:55:10.8`, `8 55 10.8`, `133.795`, `-7d14m42.53s`, `−7° 14′ 42.5″`, `-7.245` y más. Probado con 24 formas distintas.
  - [x] Si algo está mal escrito o fuera de rango, lo dice con un mensaje claro y no carga nada.
  - [x] También se puede buscar por nombre ("Proxima Centauri", "M51"). Pregunta al catálogo público SIMBAD.
- [x] ✅ **Trae imágenes de cualquier punto del cielo, en vivo.**
  - [x] El navegador lee las imágenes directo de la bodega pública de la NASA.
  - [x] Un cuaderno de apuntados dice qué imágenes cubren cada punto.
  - [x] Muestra el avance mientras carga, y un mensaje si no hay imágenes.
- [x] ✅ **Fácil de usar.** La página abre igual que antes, con los 37 lugares guardados. Las coordenadas están en una pestaña aparte para quien las necesite.

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

## Objetos de prueba

Cada uno tiene su botón en la pestaña de coordenadas.

| Objeto | Qué es | Fotos disponibles | Fechas | Qué muestra la página |
|---|---|---|---|---|
| Barnard's Star | La estrella que más rápido se mueve en el cielo (10,4″ por año) | 335 | 15 ago 2025 a 22 sep 2026 | 30 fotos en las 6 cámaras. El marcador se mueve 1,9 píxeles y la estrella lo sigue |
| Epsilon Indi B | Par de enanas marrones (4,7″ por año) | 381 | 24 abr 2025 a 2 oct 2026 | 30 fotos. El marcador se mueve 1,1 píxeles |
| WISE 0855-0714 | Enana marrón muy fría y rápida (8,2″ por año) | 238 | 5 may 2025 a 14 may 2026 | 30 fotos. El marcador se mueve 1,4 píxeles. El objeto es tan débil que no se alcanza a ver en una sola foto |
| RW Aurigae | Estrella joven que cambia de brillo | 308 | 1 sep 2025 a 16 sep 2026 | 30 fotos en las 6 cámaras |
| R Draconis | Estrella que late cada 245 días | 2.189 | 24 abr 2025 a 24 sep 2026 | 30 fotos repartidas en 17 meses |

Cada carga tardó entre 9 y 10 segundos y pesó entre 36 y 45 MB. "Fotos disponibles" cuenta solo las fotos donde el cuadro completo de 13′ cabe dentro de una cámara.

## Problemas resueltos y pendientes

- [x] **Las coordenadas de catálogo son viejas.** Las de WISE 0855 que da el reto son de 2010, y desde entonces se movió unos 2′. Para las estrellas que se mueven rápido la página calcula dónde están hoy y centra ahí la imagen.
- [x] **Las fotos salían de cabeza.** La página dibujaba el norte abajo aunque la etiqueta decía "N ↑". Ya está corregido, también en los 37 lugares guardados.
- [x] **El script de Python ya no encontraba datos nuevos.** Buscaba la versión QR2, que IRSA reemplazó por DR1. `build/resolve.py` ahora reconoce cualquier versión.
- [ ] **El movimiento es de apenas 1-2 píxeles.** El marcador ayuda y el tamaño "cerca" (6,6′) lo hace más visible, pero todavía hay que mirar con cuidado.
- [ ] **WISE 0855 es muy débil.** Probablemente solo se vea sumando muchas imágenes de la cámara 6. Falta el modo de sumar.
- [ ] **Curva de luz:** graficar el brillo contra la fecha para la estrella seleccionada. Hoy solo se grafica contra la longitud de onda.

## Consideraciones del reto

| # | Consideración | Estado | Qué falta |
|---|---|---|---|
| 1 | **Fácil de actualizar con datos nuevos** | ✅ El robot diario lo hace solo | Subirlo a GitHub y ver que corra la primera vez; no se ha podido probar allá |
| 2a | **Aprovechar las 102 bandas** | ✅ Filtro por cámara, antes y después de cargar, y orden por longitud de onda | — |
| 2b | **Sumar las imágenes de cada una de las 6 cámaras** | ❌ | Un modo "Stack" que promedie todas las visitas de una misma cámara |
| 2c | **Espectros al momento** | ✅ Clic en una estrella y sale su espectro, también en lugares buscados por coordenadas | — |
| 3 | **Sumar o restar imágenes de fechas distintas** | ⚠️ Restar sí (Difference); sumar no | Sumar rangos de fechas y restar esas sumas |
| 4 | **Que el usuario elija el campo de visión** | ✅ Tres tamaños (6,6′, 13′ y 26′), y cualquier valor de 3 a 60 por el enlace. La página avisa cuántos MB va a bajar | — |
| 5 | **Superponer datos de Gaia o WISE** | ❌ | Marcar encima las estrellas de esos catálogos. Sí se pueden pedir desde el navegador |
| 6 | **Coordenadas en el enlace para incrustar** | ✅ `?ra=…&dec=…` y `&embed=1` | — |
| 7 | **Mostrar metadatos como los flags de contaminación** | ⚠️ En las imágenes en vivo se muestran los avisos de la exposición (calidad, astrometría, aurora, resplandor) | Pintar encima los píxeles marcados; vienen comprimidos y hay que descomprimirlos |
| 8 | **Usar herramientas públicas** | ⚠️ Astropy en el build y SIMBAD para los nombres | Aladin Lite para el mapa de contexto |

## Extras opcionales

- [x] Buscar por nombre además de por coordenadas.
- [ ] Descargar el video como GIF.
