"""Keep the deck's figures in step with whatever the bundle actually holds.

The summary slide quotes a frame count and a target count. Those change every time targets are
added, and a deck quoting last week's numbers is worse than one quoting none.
"""
import io, os, re, json, sys

INDEX = 'data/out/index.json'
SLIDE = 'deck/slides/resumen.html'


def main():
    idx = json.load(io.open(INDEX, encoding='utf-8'))
    targets = idx['targets']
    frames = sum(len(t['frames']) for t in targets)
    movers = sum(1 for t in targets if t.get('moving'))
    lams = [f['lam'] for t in targets for f in t['frames']]
    mjds = [f['mjd'] for t in targets for f in t['frames']]
    months = (max(mjds) - min(mjds)) / 30.44

    s = io.open(SLIDE, encoding='utf-8').read()
    before = s

    # tile 1: the frame count
    s = re.sub(r'(color:#F1CC80">)\d[\d.,]*(</p>\s*<p style="font-size:24px; line-height:1.35; '
               r'color:#9E958A">fotos)', r'\g<1>%d\g<2>' % frames, s, count=1)
    # tile 2: targets, and how many of them move
    s = re.sub(r'(color:#F1CC80">)\d+(</p>\s*<p style="font-size:24px; line-height:1.35; '
               r'color:#9E958A">sitios)', r'\g<1>%d\g<2>' % len(targets), s, count=1)
    s = re.sub(r'sitios, y en \d+ hay algo movi&eacute;ndose',
               'sitios, y en %d hay algo movi&eacute;ndose' % movers, s, count=1)
    # tile 3: the span in whole months
    s = re.sub(r'(color:#F1CC80">)\d+(</p>\s*<p style="font-size:24px; line-height:1.35; '
               r'color:#9E958A">meses)', r'\g<1>%d\g<2>' % round(months), s, count=1)

    if s == before:
        sys.exit("nothing matched - the slide's markup moved, check it by hand")
    io.open(SLIDE, 'w', encoding='utf-8').write(s)
    print("deck figures: %d frames, %d targets (%d moving), %d months, %.2f-%.2f um"
          % (frames, len(targets), movers, round(months), min(lams), max(lams)))


if __name__ == '__main__':
    main()
