"""Build a folder that works off a USB stick with no server and no internet.

Two files to double-click at the root: the presentation and the tool. Everything they need
travels with them - typefaces embedded as data URIs, frame data as .js rather than .json so a
file:// page can load it without fetch.
"""
import io, os, re, sys, json, base64, shutil, urllib.request

OUT = 'usb/SPHEREx'
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
CSS_URL = ("https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1"
           "&family=IBM+Plex+Sans:wght@400;500;600"
           "&family=IBM+Plex+Mono:wght@400;500&display=swap")
KEEP_SUBSETS = ('latin', 'latin-ext')


def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def font_css():
    """Google's stylesheet with every woff2 pulled in as a data URI, latin subsets only."""
    css = get(CSS_URL).decode('utf-8')
    blocks = re.findall(r'/\*\s*([\w-]+)\s*\*/\s*(@font-face\s*\{.*?\})', css, re.S)
    out, total = [], 0
    for subset, block in blocks:
        if subset not in KEEP_SUBSETS:
            continue
        m = re.search(r'url\((https://[^)]+\.woff2)\)', block)
        if not m:
            continue
        data = get(m.group(1))
        total += len(data)
        uri = 'data:font/woff2;base64,' + base64.b64encode(data).decode('ascii')
        block = block.replace(m.group(1), uri)
        block = re.sub(r'\s*unicode-range:[^;]+;', '', block)   # all subsets are embedded
        out.append(re.sub(r'\n\s+', ' ', block.strip()))
    sys.stderr.write("  fonts: %d faces, %.0f KB embedded\n" % (len(out), total / 1024))
    return "<style>\n" + "\n".join(out) + "\n</style>"


def strip_font_links(html):
    html = re.sub(r'<link rel="preconnect"[^>]*>\s*', '', html)
    html = re.sub(r'<link rel="stylesheet" href="https://fonts\.googleapis\.com[^>]*>\s*', '', html)
    return html


def strip_pwa(html):
    """The offline copy runs from file://, where none of this can work."""
    html = re.sub(r'<link rel="manifest"[^>]*>\s*', '', html)
    html = re.sub(r'<script>\s*/\* A service worker only registers.*?</script>\s*', '', html, flags=re.S)
    return html


def build_tool(fonts):
    page = io.open('docs/index.html', encoding='utf-8').read()
    page = strip_pwa(strip_font_links(page))
    page = page.replace('<title>', fonts + '\n<title>', 1)
    page = page.replace('"file":"frames_', '"file":"datos/frames_')
    io.open(os.path.join(OUT, 'Herramienta.html'), 'w', encoding='utf-8').write(page)

    os.makedirs(os.path.join(OUT, 'datos'), exist_ok=True)
    n = 0
    for name in sorted(os.listdir('docs')):
        if not name.startswith('frames_') or not name.endswith('.json'):
            continue
        tid = name[len('frames_'):-len('.json')]
        payload = io.open(os.path.join('docs', name), encoding='utf-8').read()
        js = 'window.__SX=window.__SX||{};window.__SX[%s]=%s;' % (json.dumps(tid), payload)
        io.open(os.path.join(OUT, 'datos', 'frames_%s.js' % tid), 'w', encoding='utf-8').write(js)
        n += 1
    sys.stderr.write("  tool: %.1f MB page, %d data files\n"
                     % (os.path.getsize(os.path.join(OUT, 'Herramienta.html')) / 1e6, n))


DECK_SHELL = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SPHEREx Time Machine</title>
__FONTS__
<style>
*{box-sizing:border-box}
html,body{margin:0;height:100%%;background:#07070A;overflow:hidden;
  font-family:'IBM Plex Sans',Arial,sans-serif}
#stage{position:absolute;left:50%%;top:50%%;width:1920px;height:1080px;
  transform-origin:50%% 50%%;transform:translate(-50%%,-50%%)}
.slide{position:absolute;left:0;top:0;width:1920px;height:1080px;display:none}
.slide.on{display:block}
.slide>section{position:relative;width:1920px;height:1080px}
.slide aside{display:none}
#bar{position:fixed;left:0;right:0;bottom:0;height:46px;display:flex;align-items:center;
  gap:14px;padding:0 18px;background:rgba(10,10,14,.82);color:#9E958A;
  font-family:'IBM Plex Mono',monospace;font-size:13px;opacity:0;transition:opacity .25s}
#bar:hover,body.show #bar{opacity:1}
#bar button{background:#17161A;border:1px solid #2C2A30;color:#CFC7BB;border-radius:7px;
  padding:5px 11px;font:inherit;cursor:pointer}
#bar button:hover{border-color:#E08A47}
#bar .sp{flex:1}
#notes{position:fixed;left:0;right:0;bottom:46px;max-height:34%%;overflow:auto;padding:16px 22px;
  background:rgba(12,12,16,.95);border-top:1px solid #2C2A30;color:#CFC7BB;font-size:15px;
  line-height:1.5;display:none}
body.notes #notes{display:block}
</style></head>
<body>
<div id="stage">__SLIDES__</div>
<div id="bar">
  <button id="prev" type="button">&larr;</button>
  <button id="next" type="button">&rarr;</button>
  <span id="count"></span>
  <span class="sp"></span>
  <span>&larr; &rarr; pasar &middot; N notas &middot; F pantalla completa &middot; Esc salir</span>
  <button id="full" type="button">Pantalla completa</button>
</div>
<div id="notes"></div>
<script>
var slides = [].slice.call(document.querySelectorAll('.slide'));
var notes = slides.map(function (s) { var a = s.querySelector('aside'); return a ? a.textContent.trim() : ''; });
var i = 0;
function fit() {
  // clamp: a window shorter than the control bar would otherwise give a negative
  // scale and flip the slide inside out
  var k = Math.max(0.05, Math.min(innerWidth / 1920, Math.max(120, innerHeight - 46) / 1080));
  document.getElementById('stage').style.transform =
    'translate(-50%, -50%) scale(' + k + ')';
}
function show(n) {
  i = Math.max(0, Math.min(slides.length - 1, n));
  slides.forEach(function (s, k) { s.classList.toggle('on', k === i); });
  document.getElementById('count').textContent = (i + 1) + ' / ' + slides.length;
  document.getElementById('notes').textContent = notes[i] || 'Sin notas en esta diapositiva.';
}
document.getElementById('prev').onclick = function (e) { e.stopPropagation(); show(i - 1); };
document.getElementById('next').onclick = function (e) { e.stopPropagation(); show(i + 1); };
document.getElementById('full').onclick = function (e) {
  e.stopPropagation();
  if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen();
};
addEventListener('keydown', function (e) {
  if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') { e.preventDefault(); show(i + 1); }
  else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); show(i - 1); }
  else if (e.key === 'Home') show(0);
  else if (e.key === 'End') show(slides.length - 1);
  else if (e.key === 'n' || e.key === 'N') document.body.classList.toggle('notes');
  else if (e.key === 'f' || e.key === 'F') {
    if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen();
  }
});
addEventListener('click', function () { show(i + 1); });
addEventListener('resize', fit);
addEventListener('mousemove', function () {
  document.body.classList.add('show');
  clearTimeout(window.__t);
  window.__t = setTimeout(function () { document.body.classList.remove('show'); }, 2000);
});
fit(); show(0);
</script>
</body></html>
"""


def build_deck(fonts):
    index = json.load(io.open('deck/deck.json', encoding='utf-8'))
    parts = []
    for sid in index['order']:
        path = os.path.join('deck/slides', sid + '.html')
        if not os.path.exists(path):
            sys.stderr.write("  missing slide %s\n" % sid)
            continue
        parts.append('<div class="slide">' + io.open(path, encoding='utf-8').read().strip() + '</div>')
    html = DECK_SHELL.replace('__FONTS__', fonts).replace('__SLIDES__', "\n".join(parts))
    io.open(os.path.join(OUT, 'Presentacion.html'), 'w', encoding='utf-8').write(html)
    sys.stderr.write("  deck: %d slides, %.0f KB\n"
                     % (len(parts), os.path.getsize(os.path.join(OUT, 'Presentacion.html')) / 1024))


README = """SPHEREx Time Machine
====================

Dos archivos para abrir. Haz doble clic y se abren en el navegador.
No hace falta internet ni instalar nada.

  Presentacion.html   Las 7 diapositivas.
                      Flechas o clic para pasar. N muestra las notas.
                      F pantalla completa, Esc para salir.

  Herramienta.html    La herramienta. Elige un objetivo arriba y dale a play.
                      Abre en Vesta: el asteroide cruza el encuadre en 26 horas.
                      Espacio reproduce, flechas pasan fotograma,
                      clic en la imagen saca el espectro de esa fuente.

  datos/              Las imagenes. Dejalo donde esta, la herramienta
                      las busca ahi.

Si el navegador avisa de un archivo descargado de internet, es normal:
son paginas locales, no se conectan a ningun sitio.

Funciona en Chrome, Edge y Firefox. En Safari la herramienta puede
quedarse cargando: usa Chrome o Edge si lo tienes.

Todas las imagenes son datos reales de la mision SPHEREx de la NASA,
del archivo publico de IRSA/IPAC. Las posiciones de Vesta, Neptuno y
Urano vienen de las efemerides de JPL Horizons.
"""


def main():
    if os.path.exists('usb'):
        shutil.rmtree('usb')
    os.makedirs(OUT, exist_ok=True)
    sys.stderr.write("building offline bundle\n")
    fonts = font_css()
    build_tool(fonts)
    build_deck(fonts)
    io.open(os.path.join(OUT, 'LEEME.txt'), 'w', encoding='utf-8').write(README)

    total = sum(os.path.getsize(os.path.join(dp, f))
                for dp, _, fs in os.walk(OUT) for f in fs)
    print("\n%s -> %.1f MB total" % (OUT, total / 1e6))
    for dp, _, fs in sorted(os.walk(OUT)):
        for f in sorted(fs)[:4]:
            print("  %-46s %7.0f KB" % (os.path.relpath(os.path.join(dp, f), OUT),
                                        os.path.getsize(os.path.join(dp, f)) / 1024))
        if len(fs) > 4:
            print("  ... y %d archivos mas" % (len(fs) - 4))


if __name__ == '__main__':
    main()
