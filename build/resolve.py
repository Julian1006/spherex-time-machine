"""Resolve obscore observations to S3 object keys via IRSA's artifact table.

The TAP query for one week segment returns ~10k rows and takes a while, so results are
cached on disk; week segments are shared across targets and re-runs are then instant.
"""
import sys, os, re, json, collections
sys.path.insert(0, 'build')
from tap import query

PREFIX = "ibe/data/spherex/"
CACHE = "data/weekcache"
_pat = re.compile(r'/level2/([^/]+)/([^/]+)/(\d)/level2_(.+?)D(\d)_spx_')
_mem = {}


def _load_week(qr, week):
    """All science artifact URIs for one week segment, keyed by (obs_id, detector)."""
    k = qr + "_" + week
    if k in _mem:
        return _mem[k]
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, k + ".json")
    if os.path.exists(path):
        m = {tuple(json.loads(kk)): tuple(vv) for kk, vv in json.load(open(path)).items()}
        _mem[k] = m
        return m
    rows = query("SELECT TOP 200000 uri, contentlength FROM spherex.artifact "
                 "WHERE producttype='science' AND uri LIKE '%s%s/level2/%s/%%'" % (PREFIX, qr, week))
    m = {}
    for r in rows:
        g = _pat.search(r['uri'])
        if g:
            m[(g.group(4), int(g.group(5)))] = (r['uri'][len(PREFIX):], int(r['contentlength']))
    # written via a temp file so parallel builders never observe a half-written cache
    tmp = path + ".%d.tmp" % os.getpid()
    json.dump({json.dumps(list(kk)): list(vv) for kk, vv in m.items()}, open(tmp, 'w'))
    os.replace(tmp, path)
    _mem[k] = m
    sys.stderr.write("  week %s/%s -> %d files\n" % (qr, week, len(m)))
    return m


def qr_of(collection):
    return 'qr3' if 'qr3' in collection else 'qr2'


def week_of(obs_id):
    return "_".join(obs_id.split("_")[:2])


def resolve(items):
    """items: iterable of (obs_id, detector, collection). Returns {(obs_id, det): (key, size)}."""
    need = collections.defaultdict(set)
    for obs_id, det, coll in items:
        need[(qr_of(coll), week_of(obs_id))].add((obs_id, det))
    out = {}
    for (qr, week), pairs in sorted(need.items()):
        m = _load_week(qr, week)
        for p in pairs:
            if p in m:
                out[p] = m[p]
    return out
