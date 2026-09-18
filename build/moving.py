"""Find SPHEREx exposures that actually contain a moving solar system body.

A cone search cannot be done in one shot for something that moves degrees per day, so the
mission is scanned in time windows: each window asks IRSA for exposures in that window whose
detector centre lies within a cone covering the body's track, then every returned exposure is
tested against the body's interpolated position at that exposure's own timestamp.
"""
import sys, math, re
sys.path.insert(0, 'build')
from concurrent.futures import ThreadPoolExecutor
from tap import query
from ephem import track, interp

WINDOW = 20.0       # days per TAP query
MAX_SEP = 1.42      # deg from detector centre; keeps the cutout clear of the array edge
PAD = 2.0           # deg of slack on the search cone


def sep_deg(ra1, d1, ra2, d2):
    a, b = math.radians(d1), math.radians(d2)
    v = (math.sin(a) * math.sin(b) +
         math.cos(a) * math.cos(b) * math.cos(math.radians(ra1 - ra2)))
    return math.degrees(math.acos(max(-1.0, min(1.0, v))))


def det_of(did):
    m = re.search(r'/D(\d)$', did or '')
    return int(m.group(1)) if m else None


def _window(rows, t0, t1):
    seg = [r for r in rows if t0 <= r[0] <= t1]
    if len(seg) < 2:
        return None
    ras = [r[1] for r in seg]
    ref = ras[0]
    # unwrap RA around the first sample so a 0/360 crossing does not blow up the centre
    unw = [ref + ((r - ref + 180) % 360 - 180) for r in ras]
    ra_c = (sum(unw) / len(unw)) % 360
    dec_c = sum(r[2] for r in seg) / len(seg)
    rad = max(sep_deg(ra_c, dec_c, r[1], r[2]) for r in seg) + MAX_SEP + PAD
    return ra_c, dec_c, min(rad, 45.0)


def find(command, mjd_start, mjd_stop, workers=4):
    rows = track(command, mjd_start, mjd_stop, '12h')
    wins = []
    t = mjd_start
    while t < mjd_stop:
        w = _window(rows, t, min(t + WINDOW, mjd_stop))
        if w:
            wins.append((t, min(t + WINDOW, mjd_stop), w))
        t += WINDOW

    def scan(w):
        t0, t1, (ra_c, dec_c, rad) = w
        try:
            got = query("SELECT obs_id, obs_publisher_did, s_ra, s_dec, t_min, obs_collection "
                        "FROM spherex.obscore WHERE t_min BETWEEN %.5f AND %.5f AND "
                        "CONTAINS(POINT('ICRS',s_ra,s_dec),CIRCLE('ICRS',%.5f,%.5f,%.4f))=1"
                        % (t0, t1, ra_c, dec_c, rad))
        except Exception as e:
            sys.stderr.write("  window %.0f failed: %s\n" % (t0, str(e)[:120]))
            return []
        hits = []
        for r in got:
            if not r['s_ra']:
                continue
            mjd = float(r['t_min'])
            p = interp(rows, mjd)
            if not p:
                continue
            s = sep_deg(p[0], p[1], float(r['s_ra']), float(r['s_dec']))
            if s <= MAX_SEP:
                hits.append({'obs': r['obs_id'], 'det': det_of(r['obs_publisher_did']),
                             'mjd': mjd, 'coll': r['obs_collection'],
                             'ra': p[0], 'dec': p[1], 'delta': p[2], 'sep': s})
        sys.stderr.write("  window MJD %.0f: %d rows -> %d hits\n" % (t0, len(got), len(hits)))
        return hits

    with ThreadPoolExecutor(max_workers=workers) as ex:
        out = [h for part in ex.map(scan, wins) for h in part]
    out.sort(key=lambda h: h['mjd'])
    return out


def clusters(hits, gap=0.6):
    """Group hits into runs separated by less than `gap` days."""
    if not hits:
        return []
    runs, cur = [], [hits[0]]
    for h in hits[1:]:
        if h['mjd'] - cur[-1]['mjd'] <= gap:
            cur.append(h)
        else:
            runs.append(cur)
            cur = [h]
    runs.append(cur)
    return runs


def describe(runs):
    out = []
    for r in runs:
        span = r[-1]['mjd'] - r[0]['mjd']
        motion = sep_deg(r[0]['ra'], r[0]['dec'], r[-1]['ra'], r[-1]['dec'])
        out.append({'n': len(r), 'start': r[0]['mjd'], 'span_h': span * 24,
                    'motion_arcmin': motion * 60, 'motion_px': motion * 3600 / 6.15,
                    'run': r})
    out.sort(key=lambda d: -d['n'])
    return out
