"""Keep the deck's figures in step with whatever the bundle actually holds.

Two slides quote numbers: the cover and the closing one. They change every time targets are
added, and a deck quoting last week's numbers is worse than one quoting none.

Each rule finds a big number by the LABEL that sits right under it, not by the styling around
it. An earlier version matched on the exact font-size and colour of the label, which meant a
purely visual tweak to the slide silently broke this script.
"""
import io, re, json, sys

INDEX = 'data/out/index.json'

# (file, label the number is followed by, which figure to write)
RULES = [
    ('deck/slides/resumen.html', 'fotos',             'frames'),
    ('deck/slides/resumen.html', 'sitios',            'targets'),
    ('deck/slides/resumen.html', 'meses',             'months'),
    ('deck/slides/cierre.html',  'fotos reales',      'frames'),
    ('deck/slides/cierre.html',  'sitios del cielo',  'targets'),
]

# free-text mentions that also carry a figure
PHRASES = [
    ('deck/slides/resumen.html', r'sitios, y en \d+ hay algo movi&eacute;ndose',
     'sitios, y en %d hay algo movi&eacute;ndose', 'movers'),
    ('deck/slides/cierre.html', r'sitios del cielo, y en \d+ hay algo movi&eacute;ndose',
     'sitios del cielo, y en %d hay algo movi&eacute;ndose', 'movers'),
]


def main():
    idx = json.load(io.open(INDEX, encoding='utf-8'))
    targets = idx['targets']
    mjds = [f['mjd'] for t in targets for f in t['frames']]
    lams = [f['lam'] for t in targets for f in t['frames']]
    fig = {
        'frames': sum(len(t['frames']) for t in targets),
        'targets': len(targets),
        'movers': sum(1 for t in targets if t.get('moving')),
        # floored, never rounded up: the span is 15.7 months and a deck that says 16
        # is claiming sky it does not hold. The cover's own wording says "quince".
        'months': int((max(mjds) - min(mjds)) / 30.44),
    }

    files, missed = {}, []
    for path, label, key in RULES:
        s = files.get(path) or io.open(path, encoding='utf-8', newline='').read()
        pat = r'(>)\d[\d.,]*(</p>\s*<p [^>]*>%s)' % re.escape(label)
        s, n = re.subn(pat, r'\g<1>%d\g<2>' % fig[key], s, count=1)
        if not n:
            missed.append('%s: %s' % (path, label))
        files[path] = s

    for path, pat, repl, key in PHRASES:
        s = files.get(path) or io.open(path, encoding='utf-8', newline='').read()
        s, n = re.subn(pat, repl % fig[key], s, count=1)
        if not n:
            missed.append('%s: %s' % (path, pat))
        files[path] = s

    if missed:
        sys.exit("the slide markup moved, check these by hand:\n  " + "\n  ".join(missed))

    for path, s in files.items():
        io.open(path, 'w', encoding='utf-8', newline='').write(s)

    print("deck figures: %d frames, %d targets (%d moving), %d months, %.2f-%.2f um"
          % (fig['frames'], fig['targets'], fig['movers'], fig['months'], min(lams), max(lams)))


if __name__ == '__main__':
    main()
