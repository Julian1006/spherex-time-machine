"""Inject the frame index into the page template and stage both builds.

Two outputs, one template:

  docs/      a standalone static site for GitHub Pages or any static host. Carries its own
             charset and viewport meta tags, and the frame data files.
  app/dist/  the page as published to a Claude Artifact, whose host supplies those meta tags
             itself. It reuses docs/ for the data files rather than duplicating 13 MB.

Frame stacks are written as JSON carrying a base64 payload rather than raw .bin: artifact hosts
serve only standard web media types, and base64-in-JSON round-trips the float16 bytes exactly,
unlike packing them into an image and reading them back off a canvas.
"""
import sys, os, json, base64
sys.path.insert(0, 'build')
import pwa, cover, lang

SRC_TPL = 'app/template.html'
# the phone keeps the earlier, single-column page: the big dark band is made for a computer screen
CEL_TPL = 'app/template_cel.html'
LIVE_JS = 'app/live/sxlive.js'
SITE_DIR = 'docs'
ART_DIR = 'app/dist'
META = ('<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n')


# Each site page sends the visitor to the other one when it is the wrong screen for it: a phone
# (or a window under 820 px) gets cel.html, anything wider gets the dome. Decided once on arrival,
# from the screen rather than the window, so turning a phone sideways does not bounce it. Never
# from a file:// copy, which has only the one page.
SWITCH = """<script>
(function () {
  if (location.protocol === "file:") return;
  var phone = innerWidth <= 820 || (matchMedia("(pointer: coarse)").matches && Math.min(screen.width, screen.height) <= 600);
  if (phone === %s) location.replace("%s" + location.search + location.hash);
})();
</script>
"""


def main(index_path):
    idx = json.load(open(index_path))
    tpl = open(SRC_TPL, encoding='utf-8').read()
    if '/*__INDEX__*/null' not in tpl:
        raise SystemExit('template marker missing')
    for t in idx['targets']:
        t['file'] = 'frames_%s.json' % t['id']
    payload = json.dumps(idx, separators=(',', ':'))
    if '/*__LIVE__*/' not in tpl or '/*__LIVEBASE__*/"idx/"' not in tpl:
        raise SystemExit('live-search markers missing')
    # The page is written in English; its Spanish lives in app/lang/es.json, keyed by the English.
    # A sentence reworded in the template would quietly stay in English, so say so here.
    if '/*__ES__*/{}' not in tpl:
        raise SystemExit('language marker missing')
    spanish = json.load(open(lang.ES_PATH, encoding='utf-8'))
    cel = open(CEL_TPL, encoding='utf-8').read()
    needed = lang.keys(tpl, idx)
    needed += [k for k in lang.keys(cel, idx) if k not in set(needed)]
    missing, stale = lang.check(spanish, needed)
    for k in missing:
        print('no Spanish for:        ' + k[:90])
    for k in stale:
        print('Spanish for nothing:   ' + k[:90])
    tpl = tpl.replace('/*__ES__*/{}', json.dumps(spanish, ensure_ascii=False, separators=(',', ':')))
    cel = cel.replace('/*__ES__*/{}', json.dumps(spanish, ensure_ascii=False, separators=(',', ':')))
    # the engine that reads images straight from NASA's bucket lives in its own file so that
    # app/live/test.html can check it on its own; here it is folded into the single page
    tpl = tpl.replace('/*__LIVE__*/', open(LIVE_JS, encoding='utf-8').read())
    cel = cel.replace('/*__LIVE__*/', open(LIVE_JS, encoding='utf-8').read()).replace('/*__INDEX__*/null', payload)
    if '/*__COVER__*/null' not in tpl:
        raise SystemExit('cover marker missing')
    html = tpl.replace('/*__INDEX__*/null', payload)
    # the coordinate search needs docs/idx/ next to the page; the artifact build has no such folder
    art = html.replace('/*__LIVEBASE__*/"idx/"', 'null')

    os.makedirs(SITE_DIR, exist_ok=True)
    os.makedirs(ART_DIR, exist_ok=True)
    # the wall of little frames at the top of the page; the artifact build goes without it,
    # since it has nowhere to keep a picture file
    sheet = cover.build(idx, 'data/out', os.path.join(SITE_DIR, 'cover.png'))
    html = html.replace('/*__COVER__*/null', json.dumps(sheet, separators=(',', ':')))
    cel = cel.replace('/*__COVER__*/null', json.dumps(sheet, separators=(',', ':')))
    # only the site build is installable: a service worker needs https or localhost
    (site, cel), version = pwa.install(SITE_DIR, [META + SWITCH % ('true', 'cel.html') + html,
                                                  META + SWITCH % ('false', './') + cel])
    open(os.path.join(SITE_DIR, 'index.html'), 'w', encoding='utf-8').write(site)
    open(os.path.join(SITE_DIR, 'cel.html'), 'w', encoding='utf-8').write(cel)
    open(os.path.join(ART_DIR, 'index.html'), 'w', encoding='utf-8').write(art)

    data = 0
    for t in idx['targets']:
        raw = open(os.path.join('data/out', 'frames_%s.bin' % t['id']), 'rb').read()
        dst = os.path.join(SITE_DIR, t['file'])
        json.dump({'n': len(t['frames']), 'd': base64.b64encode(raw).decode('ascii')},
                  open(dst, 'w'), separators=(',', ':'))
        data += os.path.getsize(dst)

    print("%-28s %7.1f KB   (static site, installable, cache %s)"
          % ('docs/index.html', os.path.getsize(os.path.join(SITE_DIR, 'index.html')) / 1024, version))
    print("%-28s %7.1f KB   (cover: %d targets x %d frames)"
          % ('docs/cover.png', os.path.getsize(os.path.join(SITE_DIR, 'cover.png')) / 1024, len(sheet['tiles']), sheet['frames']))
    print("%-28s %7d      (sentences in Spanish, %d missing)"
          % (lang.ES_PATH, len(spanish), len(missing)))
    print("%-28s %7.1f KB   (artifact build)"
          % ('app/dist/index.html', os.path.getsize(os.path.join(ART_DIR, 'index.html')) / 1024))
    print("%-28s %7.1f MB   (%d targets, %d frames)"
          % ('docs/frames_*.json', data / 1e6, len(idx['targets']),
             sum(len(t['frames']) for t in idx['targets'])))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'data/out/index.json')
