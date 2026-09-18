"""Build a moving-target sequence: one fixed patch of sky, watched while a planet crosses it.

Frames are cut on a single sky-fixed grid centred on the middle of the body's track, so the
stars stay put and the body walks across them. Each frame also carries the body's predicted
pixel position, computed from JPL Horizons at that exposure's own timestamp, so the page can
mark where it should be rather than asking anyone to take it on trust.
"""
import sys, os, json, datetime, traceback
sys.path.insert(0, 'build')
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from resolve import resolve
from frames import image_hdu, plan, sample, out_wcs
from waves import wave_grid, wave_at
from ephem import at_times
from moving import sep_deg
from make_index import SIZE, OUT, mjd_to_iso, WORKERS

NFRAMES = 30

BODIES = [
    # slug, name, Horizons id, window, blurb
    ("neptune", "Neptune", "899", (61208.0, 61222.5),
     "Neptune, 30 astronomical units out, crossing a fixed patch of sky over twelve days in June 2026. "
     "The stars hold still; the planet does not. This is how the survey finds anything that moves."),
]


def pick_exposures(hits, window, n):
    """One exposure per pointing, spread through the window."""
    t0, t1 = window
    seen, uniq = set(), []
    for h in sorted(hits, key=lambda x: x['mjd']):
        if not (t0 <= h['mjd'] <= t1) or h['obs'] in seen:
            continue
        seen.add(h['obs'])
        uniq.append(h)
    if len(uniq) <= n:
        return uniq
    return [uniq[round(i * (len(uniq) - 1) / (n - 1))] for i in range(n)]


def build(slug, name, command, window, blurb):
    hits = json.load(open(os.path.join('data/moving', slug + '.json')))
    sel = pick_exposures(hits, window, NFRAMES)
    sys.stderr.write("%s: %d exposures in window\n" % (name, len(sel)))

    # exact positions at each exposure time, straight from Horizons
    exact = {round(m, 6): (ra, dec, dl)
             for m, ra, dec, dl in at_times(command, [round(h['mjd'], 6) for h in sel])}
    for h in sel:
        e = exact.get(round(h['mjd'], 6))
        if e:
            h['ra'], h['dec'], h['delta'] = e
    ra_c = sel[len(sel) // 2]['ra']
    dec_c = sel[len(sel) // 2]['dec']
    travel = sep_deg(sel[0]['ra'], sel[0]['dec'], sel[-1]['ra'], sel[-1]['dec'])
    sys.stderr.write("  centre %.4f %+.4f, travel %.2f arcmin (%.0f px)\n"
                     % (ra_c, dec_c, travel * 60, travel * 3600 / 6.15))

    keymap = resolve([(h['obs'], h['det'], h['coll']) for h in sel])
    ow = out_wcs(ra_c, dec_c, SIZE)

    def one(h):
        kv = keymap.get((h['obs'], h['det']))
        if not kv:
            return None
        key, fsize = kv
        try:
            hd = image_hdu(key)
            nx, ny = hd['dims'][0], hd['dims'][1]
            sx, sy, aff, resid = plan(hd['cards'], ra_c, dec_c, SIZE)
            img, _ = sample(key, hd['data_start'], nx, ny, sx, sy)
            if img is None or np.isfinite(img).mean() < 0.97:
                return None
            xs, ys, vals = wave_grid(key, fsize)
            lam, bw = wave_at(xs, ys, vals, float(sx[SIZE // 2, SIZE // 2]), float(sy[SIZE // 2, SIZE // 2]))
            mx, my = ow.world_to_pixel_values(h['ra'], h['dec'])
            f = img[np.isfinite(img)]
            return {'img': img, 'meta': {
                'obs': h['obs'], 'det': h['det'], 'mjd': round(h['mjd'], 5),
                'date': mjd_to_iso(h['mjd']), 'lam': round(lam, 4), 'bw': round(bw, 4),
                'p': [round(float(np.percentile(f, q)), 4) for q in (1, 50, 99, 99.8)],
                'min': round(float(f.min()), 3), 'max': round(float(f.max()), 3),
                'key': key, 'off': hd['data_start'], 'nx': nx, 'ny': ny,
                'aff': [round(v, 6) for v in aff], 'resid': round(resid, 3),
                'coll': h['coll'],
                'mx': round(float(mx), 2), 'my': round(float(my), 2),
                'au': round(float(h['delta']), 3)}}
        except Exception as e:
            sys.stderr.write("    %s: %s\n" % (h['obs'], str(e)[:120]))
            return None

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        res = [r for r in ex.map(one, sel) if r]
    res.sort(key=lambda r: r['meta']['mjd'])
    if not res:
        return None

    os.makedirs(OUT, exist_ok=True)
    stack = np.stack([r['img'] for r in res]).astype('<f2')
    path = 'frames_%s.bin' % slug
    open(os.path.join(OUT, path), 'wb').write(stack.tobytes())
    inside = sum(1 for r in res if 0 <= r['meta']['mx'] < SIZE and 0 <= r['meta']['my'] < SIZE)
    sys.stderr.write("  -> %d frames, %d with the body inside the cutout\n" % (len(res), inside))
    return {'id': slug, 'name': name, 'ra': ra_c, 'dec': dec_c, 'blurb': blurb,
            'file': path, 'moving': name, 'frames': [r['meta'] for r in res]}


if __name__ == '__main__':
    out = []
    for b in BODIES:
        try:
            r = build(*b)
            if r:
                out.append(r)
        except Exception:
            traceback.print_exc()
    os.makedirs(OUT, exist_ok=True)
    json.dump({'generated': datetime.datetime.utcnow().strftime('%Y-%m-%d'),
               'cutout': SIZE, 'pixelScale': 6.15, 'targets': out},
              open(os.path.join(OUT, 'index.moving.json'), 'w'), separators=(',', ':'))
    sys.stderr.write("wrote index.moving.json with %d targets\n" % len(out))
