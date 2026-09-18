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

SRC_TPL = 'app/template.html'
SITE_DIR = 'docs'
ART_DIR = 'app/dist'
META = ('<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n')


def main(index_path):
    idx = json.load(open(index_path))
    tpl = open(SRC_TPL, encoding='utf-8').read()
    if '/*__INDEX__*/null' not in tpl:
        raise SystemExit('template marker missing')
    for t in idx['targets']:
        t['file'] = 'frames_%s.json' % t['id']
    payload = json.dumps(idx, separators=(',', ':'))
    html = tpl.replace('/*__INDEX__*/null', payload)

    os.makedirs(SITE_DIR, exist_ok=True)
    os.makedirs(ART_DIR, exist_ok=True)
    open(os.path.join(SITE_DIR, 'index.html'), 'w', encoding='utf-8').write(META + html)
    open(os.path.join(ART_DIR, 'index.html'), 'w', encoding='utf-8').write(html)

    data = 0
    for t in idx['targets']:
        raw = open(os.path.join('data/out', 'frames_%s.bin' % t['id']), 'rb').read()
        dst = os.path.join(SITE_DIR, t['file'])
        json.dump({'n': len(t['frames']), 'd': base64.b64encode(raw).decode('ascii')},
                  open(dst, 'w'), separators=(',', ':'))
        data += os.path.getsize(dst)

    print("%-28s %7.1f KB   (static site, with meta tags)"
          % ('docs/index.html', os.path.getsize(os.path.join(SITE_DIR, 'index.html')) / 1024))
    print("%-28s %7.1f KB   (artifact build)"
          % ('app/dist/index.html', os.path.getsize(os.path.join(ART_DIR, 'index.html')) / 1024))
    print("%-28s %7.1f MB   (%d targets, %d frames)"
          % ('docs/frames_*.json', data / 1e6, len(idx['targets']),
             sum(len(t['frames']) for t in idx['targets'])))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'data/out/index.json')
