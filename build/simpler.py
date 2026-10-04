"""Make the display controls easy to use without taking anything away.

Five technical controls sat in front of everyone. "Black point 45.0%" tells a visitor nothing,
and the pair of percentile sliders is really one question: how bright should this look. That
question becomes one slider with words instead of numbers; the precise controls move behind
"More options" and stay in sync with it.
"""
import io, re, sys

PATH = 'app/template.html'

OLD_START = '        <h3>Display</h3>\n        <div class="field">\n          <label for="cmap">Colour map</label>'
OLD_END = '''        <p class="note">SPHEREx frames often carry a glow from bright stars just off the edge. Flattening removes
          that gradient so faint sources stand out.</p>'''

NEW = '''        <h3>Display</h3>
        <div class="field">
          <label for="bright">Brightness <b id="brightV">Normal</b></label>
          <input type="range" id="bright" min="0" max="100" step="1" value="30">
        </div>
        <div class="field">
          <label for="cmap">Colour</label>
          <select id="cmap">
            <option value="grey">Greyscale</option>
            <option value="ember" selected>Ember (infrared)</option>
            <option value="ice">Ice</option>
            <option value="spectral">Spectral</option>
          </select>
        </div>
        <button class="advtoggle" id="dispToggle" type="button" aria-expanded="false"
          aria-controls="dispAdv" style="margin:14px 0 0">More options</button>
        <div id="dispAdv" hidden>
          <div class="field">
            <label for="scale">Brightness scaling</label>
            <select id="scale">
              <option value="asinh" selected>Asinh (best for faint things)</option>
              <option value="linear">Linear</option>
              <option value="sqrt">Square root</option>
              <option value="log">Logarithmic</option>
            </select>
          </div>
          <div class="field">
            <label for="black">Black point <b id="blackV">45.0%</b></label>
            <input type="range" id="black" min="0" max="80" step="0.5" value="45">
          </div>
          <div class="field">
            <label for="white">White point <b id="whiteV">99.70%</b></label>
            <input type="range" id="white" min="0" max="1000" step="1" value="820">
          </div>
          <div class="checks">
            <label class="chk"><input type="checkbox" id="flatten"> Flatten background</label>
            <label class="chk"><input type="checkbox" id="smooth"> Smooth pixels</label>
          </div>
          <p class="note">SPHEREx frames often carry a glow from bright stars just off the edge. Flattening
            removes that gradient so faint sources stand out.</p>
        </div>'''

JS = '''
/* One slider standing in for the pair of percentile ones. It drives the white point, which is
   the control that actually decides how bright a frame reads; the precise sliders stay, and the
   two are kept in step so neither can contradict the other. */
const BRIGHT_T = b => 0.98 - (b / 100) * 0.5333;          // slider 0..100 -> whiteT 0.98..0.447, hitting the 0.82 default exactly at 30
const T_BRIGHT = t => Math.round((0.98 - t) / 0.5333 * 100);
const BRIGHT_WORD = b => b < 18 ? "Dim" : b < 42 ? "Normal" : b < 72 ? "Bright" : "Very bright";

function setBrightFromWhite() {
  const b = Math.max(0, Math.min(100, T_BRIGHT(S.whiteT)));
  $("bright").value = b;
  $("brightV").textContent = BRIGHT_WORD(b);
}

$("bright").addEventListener("input", e => {
  const b = +e.target.value;
  S.whiteT = BRIGHT_T(b);
  $("brightV").textContent = BRIGHT_WORD(b);
  $("white").value = Math.round(S.whiteT * 1000);
  $("whiteV").textContent = whitePct(S.whiteT).toFixed(2) + "%";
  draw();
});

$("dispToggle").addEventListener("click", () => {
  const open = $("dispAdv").hidden;
  $("dispAdv").hidden = !open;
  $("dispToggle").setAttribute("aria-expanded", open);
  $("dispToggle").textContent = open ? "Fewer options" : "More options";
});

setBrightFromWhite();
'''


def main():
    src = io.open(PATH, encoding='utf-8').read()

    a = src.index(OLD_START)
    b = src.index(OLD_END) + len(OLD_END)
    src = src[:a] + NEW + src[b:]

    # the precise white-point slider must push the simple one back
    old = """$("white").addEventListener("input", e => { S.whiteT = +e.target.value / 1000; $("whiteV").textContent = whitePct(S.whiteT).toFixed(2) + "%"; draw(); });"""
    new = """$("white").addEventListener("input", e => { S.whiteT = +e.target.value / 1000; $("whiteV").textContent = whitePct(S.whiteT).toFixed(2) + "%"; setBrightFromWhite(); draw(); });"""
    if old not in src:
        sys.exit('white handler not found')
    src = src.replace(old, new, 1)

    marker = '\naddEventListener("resize", () => { if (S.target) { drawTimeline(); drawSky(); } });'
    if marker not in src:
        sys.exit('js anchor missing')
    src = src.replace(marker, marker + "\n" + JS, 1)

    # the plain slider needs its own one-sentence explanation in the ? table
    anchor = '["label[for=scale]", "g-scale",'
    if anchor not in src:
        sys.exit('guide table changed')
    entry = ('["label[for=bright]", "g-bright", "The one control most people want. Drag it right and faint '
             'things lift out of the dark; drag it left and only the brightest sources stay. It is purely how '
             'the numbers are painted \u2014 the measured brightness never changes. Under More options you '
             'can set the same thing by percentile, plus a few others."], ')
    src = src.replace(anchor, entry + anchor, 1)

    io.open(PATH, 'w', encoding='utf-8').write(src)
    print('display simplified')


if __name__ == '__main__':
    main()
