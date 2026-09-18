"""JPL Horizons ephemerides for solar system bodies, in MJD / degrees.

Two modes: a regularly sampled track for searching, and exact positions at a list of
times for the exposures that actually matter.
"""
import urllib.request, urllib.parse, time, sys, re, os, json

API = "https://ssd.jpl.nasa.gov/api/horizons.api"
CACHE = 'data/ephem'
MJD0 = 2400000.5


def _call(params, retries=3):
    q = urllib.parse.urlencode(params)
    last = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(API + "?" + q, timeout=180) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            last = e
            sys.stderr.write("  horizons retry %d: %s\n" % (i + 1, str(e)[:160]))
            time.sleep(4)
    raise last


def _parse(txt):
    """Rows of (mjd, ra_deg, dec_deg, delta_au). Horizons pads absent columns with n.a."""
    body = re.search(r'\$\$SOE\n(.*?)\$\$EOE', txt, re.S)
    if not body:
        raise RuntimeError("no ephemeris block:\n" + txt[:600])
    out = []
    for line in body.group(1).splitlines():
        nums = re.findall(r'-?\d+\.\d+(?:[Ee][-+]?\d+)?', line)
        if len(nums) < 4:
            continue
        jd = float(nums[0])
        ra, dec = float(nums[1]), float(nums[2])
        delta = float(nums[-2]) if len(nums) >= 5 else float(nums[-1])
        out.append((jd - MJD0, ra, dec, delta))
    return out


def _base(command):
    return {
        'format': 'text', 'COMMAND': "'%s'" % command, 'OBJ_DATA': "'NO'",
        'MAKE_EPHEM': "'YES'", 'EPHEM_TYPE': "'OBSERVER'", 'CENTER': "'500@399'",
        'QUANTITIES': "'1,20'", 'ANG_FORMAT': "'DEG'", 'CAL_FORMAT': "'JD'",
        'CSV_FORMAT': "'NO'", 'APPARENT': "'AIRLESS'",
    }


def track(command, mjd_start, mjd_stop, step='6h'):
    """Regularly sampled geocentric track, cached on disk."""
    os.makedirs(CACHE, exist_ok=True)
    key = re.sub(r'\W+', '_', "%s_%d_%d_%s" % (command, mjd_start, mjd_stop, step))
    path = os.path.join(CACHE, key + '.json')
    if os.path.exists(path):
        return json.load(open(path))
    p = _base(command)
    p['START_TIME'] = "'JD %.5f'" % (mjd_start + MJD0)
    p['STOP_TIME'] = "'JD %.5f'" % (mjd_stop + MJD0)
    p['STEP_SIZE'] = "'%s'" % step
    rows = _parse(_call(p))
    json.dump(rows, open(path, 'w'))
    sys.stderr.write("  ephem %s: %d samples\n" % (command, len(rows)))
    return rows


def at_times(command, mjds):
    """Exact positions at specific times (Horizons TLIST), in batches."""
    out = []
    for i in range(0, len(mjds), 40):
        chunk = mjds[i:i + 40]
        p = _base(command)
        p['TLIST'] = ",".join("%.8f" % (m + MJD0) for m in chunk)
        p['TLIST_TYPE'] = "'JD'"
        out += _parse(_call(p))
    return out


def interp(rows, mjd):
    """Linear interpolation on the sampled track. Returns (ra, dec, delta_au) or None."""
    if not rows or mjd < rows[0][0] or mjd > rows[-1][0]:
        return None
    lo, hi = 0, len(rows) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if rows[mid][0] <= mjd:
            lo = mid
        else:
            hi = mid
    t0, ra0, d0, r0 = rows[lo]
    t1, ra1, d1, r1 = rows[hi]
    f = 0.0 if t1 == t0 else (mjd - t0) / (t1 - t0)
    dra = ((ra1 - ra0 + 180) % 360) - 180           # shortest way round
    return ((ra0 + f * dra) % 360, d0 + f * (d1 - d0), r0 + f * (r1 - r0))
