"""Build the SPHEREx Time Machine data bundle: reprojected cutout stacks + metadata index."""
import sys, os, re, json, math, datetime, traceback
sys.path.insert(0, 'build')
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from tap import query
from resolve import resolve
from frames import image_hdu, plan, sample
from waves import wave_grid, wave_at

SIZE    = 128
NFRAMES = 30
MAX_SEP = 1.42          # deg from detector centre; keeps the cutout box clear of the edge
OUT     = 'data/out'
WORKERS = 8

TARGETS = [
 ("nep", "North Ecliptic Pole", 270.000, 66.561,
  "SPHEREx's northern deep field. Revisited on nearly every orbit, this is the most densely time-sampled patch of sky in the whole survey."),
 ("sep", "South Ecliptic Pole", 90.000, -66.561,
  "The southern deep field, counterpart to the NEP. Repeated visits stack up to reach the faintest sources SPHEREx can detect."),
 ("m42", "Orion Nebula", 83.822, -5.391,
  "The nearest massive star-forming region. Warm dust and ices make it spectacularly bright across SPHEREx's infrared bands."),
 ("m31", "Andromeda Galaxy", 10.685, 41.269,
  "Our nearest large galactic neighbour, 2.5 million light-years away and wide enough to span many SPHEREx pointings."),
 ("m45", "Pleiades", 56.750, 24.117,
  "A young open cluster wrapped in reflection nebulosity that its hot blue stars light from within."),
 ("30dor", "Tarantula Nebula", 84.676, -69.101,
  "The most active starburst region in the Local Group, sitting inside the Large Magellanic Cloud."),
 ("rhooph", "Rho Ophiuchi", 246.789, -24.617,
  "One of the closest star-forming clouds. Dust here blocks visible light almost completely but glows in the infrared."),
 ("carina", "Carina Nebula", 161.265, -59.684,
  "A vast nebula holding some of the most massive and unstable stars known, including Eta Carinae."),
 ("helix", "Helix Nebula", 337.411, -20.837,
  "A dying Sun-like star casting off its outer layers: the nearest bright planetary nebula."),
 ("m13", "Hercules Cluster", 250.423, 36.460,
  "A globular cluster of several hundred thousand ancient stars, densely packed and ideal for spotting anything that moves."),

    # --- added later: a wider sweep of the sky, shown under Advanced ---
    ("m16", "Eagle Nebula", 274.700, -13.807,
     "Home of the Pillars of Creation, columns of cold gas where stars are still condensing."),
    ("m17", "Omega Nebula", 275.196, -16.172,
     "One of the brightest and most massive star-forming regions in the galaxy."),
    ("rosette", "Rosette Nebula", 97.950, 4.950,
     "A ring of gas around a young cluster whose winds have blown out the middle."),
    ("california", "California Nebula", 60.000, 36.417,
     "A long ribbon of hydrogen in Perseus, faint to the eye but prominent in the infrared."),
    ("horsehead", "Horsehead Nebula", 85.246, -2.458,
     "A pillar of dark dust silhouetted against glowing gas, beside the belt of Orion."),
    ("catseye", "Cat's Eye Nebula", 269.639, 66.633,
     "A dying star shedding concentric shells of gas, close to the northern deep field."),
    ("m27", "Dumbbell Nebula", 299.902, 22.721,
     "A bright planetary nebula, the cast-off atmosphere of a star like the Sun."),
    ("m1", "Crab Nebula", 83.633, 22.015,
     "The wreckage of a star that exploded in 1054, still expanding today."),
    ("m57", "Ring Nebula", 283.396, 33.029,
     "A near-perfect ring of glowing gas around a white dwarf in Lyra."),
    ("omegacen", "Omega Centauri", 201.697, -47.480,
     "The largest globular cluster in the galaxy, some ten million stars bound together."),
    ("tuc47", "47 Tucanae", 6.024, -72.081,
     "A dense southern globular cluster, second only to Omega Centauri in brightness."),
    ("m22", "Cluster M22", 279.100, -23.905,
     "One of the nearest globular clusters, seen through the crowded fields of Sagittarius."),
    ("m3", "Cluster M3", 205.548, 28.377,
     "Half a million ancient stars, far above the plane of the galaxy."),
    ("m5", "Cluster M5", 229.638, 2.081,
     "One of the oldest globular clusters known, around twelve billion years."),
    ("doublecl", "Double Cluster", 34.750, 57.133,
     "Two young open clusters side by side in Perseus, both only a few million years old."),
    ("m44", "Beehive Cluster", 130.100, 19.667,
     "A loose open cluster near enough to see without a telescope on a dark night."),
    ("m11", "Wild Duck Cluster", 282.766, -6.272,
     "One of the richest open clusters, packed into a small patch of the Milky Way."),
    ("m51", "Whirlpool Galaxy", 202.470, 47.195,
     "A spiral galaxy caught mid-interaction with a smaller companion on its arm."),
    ("m104", "Sombrero Galaxy", 189.998, -11.623,
     "An edge-on spiral with a dust lane so sharp it looks drawn on."),
    ("m81", "Bode's Galaxy", 148.888, 69.065,
     "A grand design spiral, one of the brightest galaxies in the northern sky."),
    ("m82", "Cigar Galaxy", 148.968, 69.680,
     "A starburst galaxy driving plumes of gas out of its own core."),
    ("m33", "Triangulum Galaxy", 23.462, 30.660,
     "The third largest galaxy in the Local Group, seen almost face on."),
    ("cena", "Centaurus A", 201.365, -43.019,
     "A giant elliptical galaxy with a dust lane across it, the remains of a merger."),
    ("smc", "Small Magellanic Cloud", 13.187, -72.829,
     "A dwarf galaxy orbiting the Milky Way, visible from the southern hemisphere."),
]


def mjd_to_iso(mjd):
    return (datetime.datetime(1858, 11, 17) + datetime.timedelta(days=float(mjd))).strftime('%Y-%m-%d')


def sep_deg(ra1, d1, ra2, d2):
    a, b = math.radians(d1), math.radians(d2)
    dra = math.radians(ra1 - ra2)
    v = math.sin(a) * math.sin(b) + math.cos(a) * math.cos(b) * math.cos(dra)
    return math.degrees(math.acos(max(-1.0, min(1.0, v))))


def det_of(did):
    m = re.search(r'/D(\d)$', did or '')
    return int(m.group(1)) if m else None


def candidates(ra, dec):
    rows = query("SELECT TOP 40000 obs_id, obs_publisher_did, s_ra, s_dec, t_min, obs_collection "
                 "FROM spherex.obscore WHERE CONTAINS(POINT('ICRS',%.6f,%.6f),s_region)=1" % (ra, dec))
    out = []
    for r in rows:
        d = det_of(r['obs_publisher_did'])
        if d is None or not r['s_ra']:
            continue
        s = sep_deg(ra, dec, float(r['s_ra']), float(r['s_dec']))
        if s > MAX_SEP:
            continue
        out.append({'obs': r['obs_id'], 'det': d, 'mjd': float(r['t_min']),
                    'coll': r['obs_collection'], 'sep': s})
    out.sort(key=lambda x: x['mjd'])
    return out


def pick(cands, n):
    """Choose n slots evenly spaced through the time-ordered candidates.

    SPHEREx revisits a given patch in bursts rather than at a steady cadence, so binning by
    elapsed time leaves most bins empty. Spacing by position in the time-ordered list keeps
    the full baseline while preserving the real observing pattern, including the ~90 s
    consecutive exposures within a visit that reveal fast-moving objects.
    """
    if not cands:
        return []
    n = min(n, len(cands))
    slots = []
    for i in range(n):
        j = round(i * (len(cands) - 1) / max(n - 1, 1))
        tries = [cands[k] for k in (j, j + 1, j - 1, j + 2) if 0 <= k < len(cands)]
        slots.append(tries[:3])
    return slots


def build_frame(c, ra, dec, keymap):
    kv = keymap.get((c['obs'], c['det']))
    if not kv:
        return None
    key, fsize = kv
    h = image_hdu(key)
    nx, ny = h['dims'][0], h['dims'][1]
    sx, sy, aff, resid = plan(h['cards'], ra, dec, SIZE)
    img, nbytes = sample(key, h['data_start'], nx, ny, sx, sy)
    if img is None:
        return None
    finite = np.isfinite(img)
    if finite.mean() < 0.97:
        return None
    f = img[finite]
    xs, ys, vals = wave_grid(key, fsize)
    lam, bw = wave_at(xs, ys, vals, float(sx[SIZE // 2, SIZE // 2]), float(sy[SIZE // 2, SIZE // 2]))
    p = [float(np.percentile(f, q)) for q in (1, 50, 99, 99.8)]
    return {
        'img': img,
        'meta': {'obs': c['obs'], 'det': c['det'], 'mjd': round(c['mjd'], 5),
                 'date': mjd_to_iso(c['mjd']), 'lam': round(lam, 4), 'bw': round(bw, 4),
                 'p': [round(v, 4) for v in p],
                 'min': round(float(f.min()), 3), 'max': round(float(f.max()), 3),
                 'key': key, 'off': h['data_start'], 'nx': nx, 'ny': ny,
                 'aff': [round(v, 6) for v in aff], 'resid': round(resid, 3),
                 'coll': c['coll']}
    }


def do_target(slug, name, ra, dec, blurb):
    sys.stderr.write("\n=== %s (%s) ===\n" % (name, slug))
    cands = candidates(ra, dec)
    sys.stderr.write("  %d usable candidates\n" % len(cands))
    if not cands:
        return None
    bins = pick(cands, NFRAMES)
    need = [c for b in bins for c in b[:3]]                     # up to 3 tries per time bin
    keymap = resolve([(c['obs'], c['det'], c['coll']) for c in need])
    sys.stderr.write("  resolved %d/%d S3 keys\n" % (len(keymap), len(need)))

    def per_bin(b):
        for c in b[:3]:
            try:
                r = build_frame(c, ra, dec, keymap)
                if r:
                    return r
            except Exception as e:
                sys.stderr.write("    %s: %s\n" % (c['obs'], str(e)[:140]))
        return None

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        results = list(ex.map(per_bin, bins))
    frames, seen = [], set()
    for r in results:
        if r and r['meta']['obs'] + str(r['meta']['det']) not in seen:
            seen.add(r['meta']['obs'] + str(r['meta']['det']))
            frames.append(r)
    frames.sort(key=lambda r: r['meta']['mjd'])
    if not frames:
        return None

    os.makedirs(OUT, exist_ok=True)
    stack = np.stack([f['img'] for f in frames]).astype('<f2')
    path = 'frames_%s.bin' % slug
    open(os.path.join(OUT, path), 'wb').write(stack.tobytes())
    sys.stderr.write("  -> %d frames, %.0f KB\n" % (len(frames), stack.nbytes / 1024))
    return {'id': slug, 'name': name, 'ra': ra, 'dec': dec, 'blurb': blurb,
            'file': path, 'frames': [f['meta'] for f in frames]}


def save(out, path):
    os.makedirs(OUT, exist_ok=True)
    idx = {'generated': datetime.datetime.utcnow().strftime('%Y-%m-%d'),
           'cutout': SIZE, 'pixelScale': 6.15, 'targets': out}
    json.dump(idx, open(path, 'w'), separators=(',', ':'))
    sys.stderr.write("  saved index: %d targets, %d frames\n"
                     % (len(out), sum(len(t['frames']) for t in out)))
    sys.stderr.flush()


if __name__ == '__main__':
    only = [a for a in sys.argv[1:] if not a.startswith('-')]
    resume = '--resume' in sys.argv
    path = os.path.join(OUT, 'index%s.json' % ('' if not only else '.' + '_'.join(only)))

    out, done = [], set()
    if resume and os.path.exists(path):
        out = json.load(open(path))['targets']
        done = {t['id'] for t in out}
        sys.stderr.write("resuming; already built: %s\n" % (", ".join(sorted(done)) or "none"))

    for t in TARGETS:
        if only and t[0] not in only:
            continue
        if t[0] in done:
            continue
        try:
            r = do_target(*t)
            if r:
                out.append(r)
                # written after every target so a long run is never lost
                out.sort(key=lambda x: [k[0] for k in TARGETS].index(x['id']))
                save(out, path)
        except Exception:
            traceback.print_exc()
            sys.stderr.flush()
    save(out, path)
