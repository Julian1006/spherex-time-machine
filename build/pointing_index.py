"""Build the pointing index: where SPHEREx was looking in every exposure NASA has released.

The page reads image pixels straight from NASA's public bucket, but nothing a browser is
allowed to call will tell it *which* exposures cover a given spot: IRSA's search services send
no CORS headers, and they are slow. So that one question is answered ahead of time, from the
bucket itself:

  1. list the bucket to see which exposures exist, in which release and processing folder;
  2. read a few kilobytes of one file per exposure - the part of its header that holds the
     astrometry and the time;
  3. boil that down to a single attitude. The six detectors keep a fixed layout, so one
     attitude describes all six images, and the page can work out the rest.

    python build/pointing_index.py              # add whatever is new since the last run
    python build/pointing_index.py --full       # read every exposure again
    python build/pointing_index.py --calibrate RELEASE:OBS_ID ...   # refit the focal-plane model

Standard library only, so it runs unchanged on a laptop and in GitHub Actions. It depends on
nothing but the bucket: no IRSA query is involved.

Always the newest version: when the same week of data exists in more than one release, the
data release beats the quick release and the higher number beats the lower, so the day NASA
uploads a newer release the next run switches to it by itself.

Written to docs/idx/:
    manifest.json   the focal-plane model, plus one entry per week segment: its release,
                    processing folders, time range and a coarse map of the sky it touches
    <segment>.bin   one record per exposure: attitude, time, exposure number and which of the
                    six detector images exist (and in which processing folder)
"""
import sys, os, re, json, math, time, struct, base64, hashlib, argparse, datetime, threading, collections
import http.client, urllib.parse
import concurrent.futures as cf

HOST = "nasa-irsa-spherex.s3.amazonaws.com"
OUT = "docs/idx"
MODEL = "build/focal_plane.json"
BLOCK = 2880
D2R = math.pi / 180.0
CELL = 5                      # degrees; the coverage map is a 72 x 36 grid in RA and Dec
NRA, NDEC = 360 // CELL, 180 // CELL
THREADS = int(os.environ.get("SX_THREADS", "96"))     # simultaneous small requests to the bucket
CHUNK = 12                    # segments handled at a time, to keep memory and progress in check
RECENT = 6                    # newest segments of each release are listed again every day: they still grow
WINDOW = (11520, 23039)       # the bytes of a file that hold its astrometry and its time
ANCHORS = ((1019.5, 1019.5), (119.5, 1019.5), (1919.5, 1019.5))   # centre, left and right pixels
PREFER = (2, 5, 3, 6, 1, 4)   # which detector's header to read: the middle of the focal plane first

log = lambda *a: (sys.stderr.write(" ".join(str(x) for x in a) + "\n"), sys.stderr.flush())


# ---------------------------------------------------------------- the bucket

_local = threading.local()

def s3(path, headers=None, tries=7):
    """GET from the bucket over a kept-alive connection. Returns (status, body)."""
    for i in range(tries):
        c = getattr(_local, "c", None)
        try:
            if c is None:
                c = _local.c = http.client.HTTPSConnection(HOST, timeout=90)
            c.request("GET", path, headers=headers or {})
            r = c.getresponse()
            body = r.read()
            if r.status in (200, 206, 404):
                return r.status, body
        except Exception:
            pass
        try:
            c.close()
        except Exception:
            pass
        _local.c = None
        time.sleep(min(30, 0.5 * 2 ** i))
    raise RuntimeError("the bucket did not answer for " + path)


def s3_list(prefix, delimiter="/"):
    """Folders and files under a bucket prefix, following pagination."""
    folders, files, token = [], [], None
    while True:
        q = {"list-type": "2", "prefix": prefix}
        if delimiter:
            q["delimiter"] = delimiter
        if token:
            q["continuation-token"] = token
        x = s3("/?" + urllib.parse.urlencode(q))[1].decode()
        folders += re.findall(r"<CommonPrefixes><Prefix>([^<]*)</Prefix>", x)
        files += re.findall(r"<Key>([^<]*)</Key>", x)
        m = re.search(r"<NextContinuationToken>([^<]*)<", x)
        if "<IsTruncated>true" not in x or not m:
            return folders, files
        token = m.group(1)


def s3_range(key, start, end):
    status, body = s3("/" + key, {"Range": "bytes=%d-%d" % (start, end)})
    if status == 404:
        raise FileNotFoundError(key)
    return body


# ---------------------------------------------------------------- small vector kit

def unit(ra, dec):
    a, d = ra * D2R, dec * D2R
    return (math.cos(d) * math.cos(a), math.cos(d) * math.sin(a), math.sin(d))

def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)

def norm(a):
    n = math.sqrt(dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n)

def radec(p):
    p = norm(p)
    return math.degrees(math.atan2(p[1], p[0])) % 360.0, math.degrees(math.asin(max(-1.0, min(1.0, p[2]))))

def east_north(z):
    """Unit vectors toward east and north at direction z."""
    ra, dec = radec(z)
    a, d = ra * D2R, dec * D2R
    return (-math.sin(a), math.cos(a), 0.0), (-math.sin(d) * math.cos(a), -math.sin(d) * math.sin(a), math.cos(d))

def model_dir(X, Y):
    """Direction, in the instrument's own axes, of tangent-plane point (X, Y) degrees."""
    return norm((math.tan(X * D2R), math.tan(Y * D2R), 1.0))

def axes(ra0, dec0, pa):
    """x, y, z unit vectors of the instrument frame on the sky."""
    z = unit(ra0, dec0)
    e, n = east_north(z)
    x = add(mul(n, math.cos(pa * D2R)), mul(e, math.sin(pa * D2R)))
    return x, cross(z, x), z


# ---------------------------------------------------------------- FITS headers and astrometry

def card_value(text):
    v = text.strip()
    if v.startswith("'"):
        return v[1:v.index("'", 1)].strip()
    v = v.split("/")[0].strip()
    try:
        return float(v) if any(c in v for c in ".eE") else int(v)
    except ValueError:
        return v

def loose_cards(buf):
    """Keyword cards found anywhere in a block of header bytes that starts on a card boundary."""
    h = {}
    for i in range(0, len(buf) - 79, 80):
        card = buf[i:i + 80]
        if card[8:10] == b"= ":
            h[card[:8].decode("ascii", "replace").strip()] = card_value(card[10:].decode("ascii", "replace"))
    return h

def parse_header(buf, off):
    """One whole header starting at byte `off`: (cards, data_start, next_hdu), or None if cut short."""
    h, p, done = {}, off, False
    while not done:
        if p + BLOCK > len(buf):
            return None
        for i in range(36):
            card = buf[p + i * 80: p + i * 80 + 80]
            if card.startswith(b"END     "):
                done = True
                break
            if card[8:10] == b"= ":
                h[card[:8].decode("ascii", "replace").strip()] = card_value(card[10:].decode("ascii", "replace"))
        p += BLOCK
    naxis = h.get("NAXIS", 0)
    npix = 1 if naxis else 0
    for i in range(1, naxis + 1):
        npix *= h["NAXIS%d" % i]
    nbytes = abs(h.get("BITPIX", 8)) // 8 * h.get("GCOUNT", 1) * (h.get("PCOUNT", 0) + npix)
    return h, p, p + (nbytes + BLOCK - 1) // BLOCK * BLOCK

def image_header(key):
    """The complete IMAGE header of a file."""
    buf = s3_range(key, 0, 65535)
    off = 0
    for _ in range(4):
        r = parse_header(buf, off)
        if r is None:
            break
        if r[0].get("EXTNAME") == "IMAGE":
            return r[0]
        off = r[2]
    raise RuntimeError("no IMAGE header in " + key)

def pointing_cards(key):
    """Just the astrometry and time cards of a file: one request of 11.5 KB.

    The window is a guess that has held for every file seen; if it ever misses, the whole
    header is read instead, so a change of layout costs time rather than correctness.
    """
    h = loose_cards(s3_range(key, *WINDOW))
    if "WCSAXES" in h and "MJD-OBS" in h and "A_ORDER" in h and "CRVAL2" in h:
        return h
    return image_header(key)

def pixel_to_vec(h, x, y):
    """Unit vector on the sky of 0-based detector pixel (x, y), through the header's TAN-SIP."""
    u, v = x + 1 - h["CRPIX1"], y + 1 - h["CRPIX2"]
    def sip(name):
        s = 0.0
        order = int(h.get(name + "_ORDER", 0))
        for p in range(order + 1):
            for q in range(order + 1 - p):
                c = h.get("%s_%d_%d" % (name, p, q))
                if c:
                    s += c * u ** p * v ** q
        return s
    U, V = u + sip("A"), v + sip("B")
    d1, d2 = h.get("CDELT1", 1.0), h.get("CDELT2", 1.0)
    if "CD1_1" in h:
        c11, c12, c21, c22 = h["CD1_1"], h.get("CD1_2", 0.0), h.get("CD2_1", 0.0), h["CD2_2"]
    else:
        c11, c12, c21, c22 = d1 * h.get("PC1_1", 1.0), d1 * h.get("PC1_2", 0.0), d2 * h.get("PC2_1", 0.0), d2 * h.get("PC2_2", 1.0)
    xi, eta = (c11 * U + c12 * V) * D2R, (c21 * U + c22 * V) * D2R
    c = unit(h["CRVAL1"], h["CRVAL2"])
    e, n = east_north(c)
    return norm(add(c, add(mul(e, xi), mul(n, eta))))

def wave_table(key):
    """The WCS-WAVE lookup table at the end of a file: control points and (um, um) values."""
    buf = s3("/" + key, {"Range": "bytes=-%d" % (10 * BLOCK)})[1]
    for b in range(len(buf) // BLOCK - 1, -1, -1):
        off = b * BLOCK
        if buf[off:off + 20] != b"XTENSION= 'BINTABLE'":
            continue
        r = parse_header(buf, off)
        if r is None or r[0].get("EXTNAME") != "WCS-WAVE":
            continue
        h, pos, got = r[0], r[1], {}
        for i in range(1, int(h["TFIELDS"]) + 1):
            m = re.match(r"\s*(\d*)\s*([A-Z])", str(h["TFORM%d" % i]))
            count, code = int(m.group(1) or 1), {"J": ">i", "E": ">f", "D": ">d", "I": ">h"}[m.group(2)]
            width = struct.calcsize(code)
            got[h["TTYPE%d" % i]] = [struct.unpack_from(code, buf, pos + k * width)[0] for k in range(count)]
            pos += count * width
        return {"xs": got["X"], "ys": got["Y"], "values": [round(v, 6) for v in got["VALUES"]]}
    raise RuntimeError("no WCS-WAVE table in " + key)


# ---------------------------------------------------------------- releases, segments, files

def rank(release):
    """Newer wins: a data release beats a quick release, then the higher number."""
    m = re.match(r"([a-z]+)(\d+)$", release)
    return (1 if m.group(1) == "dr" else 0, int(m.group(2)))

def version_rank(ver):
    """Among processing folders holding the same image: newer pipeline, later date, then a retry."""
    m = re.search(r"v(\d+)-(\d{4})-(\d{3})", ver)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), "retry" in ver) if m else (0, 0, 0, False)

def bucket_releases():
    folders, _ = s3_list("")
    return sorted((f.strip("/") for f in folders if re.match(r"^(dr|qr)\d+/$", f)), key=rank, reverse=True)

def bucket_segments(release):
    folders, _ = s3_list(release + "/level2/")
    return sorted(f.split("/")[2] for f in folders)

_key = re.compile(r"^[a-z]+\d+/level2/[^/]+/([^/]+)/(\d)/level2_(.+?)D(\d)_spx_.+\.fits$")

def scan_segment(release, seg):
    """Every image file of a segment: ({obs_id: {detector: folder}}, folders most used first)."""
    _, files = s3_list("%s/level2/%s/" % (release, seg), delimiter=None)
    best = {}
    scan_segment.folders[(release, seg)] = {k.split("/")[3] for k in files if k.count("/") > 3}
    for k in files:
        m = _key.match(k)
        if not m or m.group(2) != m.group(4):
            continue
        ver, det, obs = m.group(1), int(m.group(2)), m.group(3)
        cur = best.get((obs, det))
        if cur is None or version_rank(ver) > version_rank(cur):
            best[(obs, det)] = ver
    versions = [v for v, _ in collections.Counter(best.values()).most_common()]
    exps = {}
    for (obs, det), ver in best.items():
        exps.setdefault(obs, {})[det] = ver
    return exps, versions

scan_segment.folders = {}             # every processing folder seen under a segment, used or not


def key_of(release, seg, ver, obs, det):
    return "%s/level2/%s/%s/%d/level2_%sD%d_spx_%s.fits" % (release, seg, ver, det, obs, det, ver)


# ---------------------------------------------------------------- attitude of one exposure

def attitude(h, det, model):
    """(ra0, dec0, pa) of the instrument frame from one detector's own astrometry.

    Three pixels of that detector are placed on the sky with the file's TAN-SIP solution and
    matched to where the model says those pixels sit in the instrument frame. The centre
    pixel is matched exactly; the left-to-right direction fixes the roll about it.
    """
    c, l, r = (pixel_to_vec(h, x, y) for x, y in ANCHORS)
    C, L, R = (model_dir(*p) for p in model["anchors"][str(det)])
    b, B = norm(sub(r, l)), norm(sub(R, L))
    t1, t2 = c, norm(cross(c, b)); t3 = cross(t1, t2)
    T1, T2 = C, norm(cross(C, B)); T3 = cross(T1, T2)
    rot = lambda v: add(add(mul(t1, dot(T1, v)), mul(t2, dot(T2, v))), mul(t3, dot(T3, v)))
    z, x = norm(rot((0, 0, 1))), norm(rot((1, 0, 0)))
    e, n = east_north(z)
    ra0, dec0 = radec(z)
    return ra0, dec0, math.degrees(math.atan2(dot(x, e), dot(x, n)))


# ---------------------------------------------------------------- one segment -> one file

def coverage(atts, model):
    """Bitmap of the 5-degree sky cells any exposure of the segment comes near."""
    bits = bytearray(NRA * NDEC // 8)
    x0, x1, y0, y1 = model["bounds"]
    pad, step = 2.0, 1.0                               # sample a padded footprint finely enough to hit every cell it touches
    xs = [x0 - pad + k * step for k in range(int((x1 - x0 + 2 * pad) / step) + 2)]
    ys = [y0 - pad + k * step for k in range(int((y1 - y0 + 2 * pad) / step) + 2)]
    grid = [(math.tan(X * D2R), math.tan(Y * D2R)) for X in xs for Y in ys]
    seen = set()
    for ra0, dec0, pa in atts:
        x, y, z = axes(ra0, dec0, pa)
        for tx, ty in grid:
            p = (z[0] + tx * x[0] + ty * y[0], z[1] + tx * x[1] + ty * y[1], z[2] + tx * x[2] + ty * y[2])
            r = math.sqrt(p[0] * p[0] + p[1] * p[1] + p[2] * p[2])
            dec = math.degrees(math.asin(p[2] / r))
            j = min(NDEC - 1, int((dec + 90.0) / CELL))
            if abs(dec) >= 75.0:                       # cells get thin near the poles: take the whole ring
                seen.add((j, -1))
            else:
                seen.add((j, min(NRA - 1, int((math.degrees(math.atan2(p[1], p[0])) % 360.0) / CELL))))
    for j, i in seen:
        for ii in (range(NRA) if i < 0 else (i,)):
            k = j * NRA + ii
            bits[k >> 3] |= 1 << (k & 7)
    return base64.b64encode(bytes(bits)).decode()


def read_bin(path):
    """Records of an existing segment file, keyed by (exposure number, sub-exposure)."""
    buf = open(path, "rb").read()
    if buf[:4] != b"SXP1":
        return {}
    n = struct.unpack_from("<I", buf, 4)[0]
    o = 16
    f = lambda: struct.unpack_from("<%df" % n, buf, o)
    ra = f(); o += 4 * n; dec = f(); o += 4 * n; pa = f(); o += 4 * n; t = f(); o += 4 * n
    num = struct.unpack_from("<%dH" % n, buf, o); o += 2 * n
    bits = struct.unpack_from("<%dH" % n, buf, o); o += 2 * n
    sub_ = struct.unpack_from("<%dB" % n, buf, o)
    return {(num[i], sub_[i]): (bits[i], ra[i], dec[i], pa[i], t[i]) for i in range(n)}


def plan_segment(release, seg, old_entry, full):
    """List a segment and decide which exposures need their header read.

    Returns (versions, known, todo): `known` are records carried over unchanged from the
    last run, `todo` are (num, sub, bits, detector, key) still to be measured.
    """
    exps, versions = scan_segment(release, seg)
    if len(versions) > 3:
        log("  %s: %d processing folders, keeping the three most used" % (seg, len(versions)))
    versions = versions[:3]
    old, t0_old = {}, 0
    path = os.path.join(OUT, seg + ".bin")
    if not full and old_entry and old_entry.get("r") == [release] and old_entry.get("v") == [versions] and os.path.exists(path):
        old, t0_old = read_bin(path), old_entry["t0"]
    known, todo = [], []
    for obs, dets in exps.items():
        m = re.match(r"^%s_(\d+)_(\d+)$" % re.escape(seg), obs)
        if not m or int(m.group(1)) > 65535 or int(m.group(2)) > 255 or "%s_%04d_%d" % (seg, int(m.group(1)), int(m.group(2))) != obs:
            continue
        num, sb, bits = int(m.group(1)), int(m.group(2)), 0
        for d, ver in dets.items():
            if ver in versions:
                bits |= (versions.index(ver) + 1) << (2 * (d - 1))
        if not bits:
            continue
        o = old.get((num, sb))
        if o and (o[0] & 0x0FFF) == bits:
            known.append((t0_old + o[4], (o[1], o[2], o[3]), num, sb, o[0]))
            continue
        d = next(d for d in PREFER if (bits >> (2 * (d - 1))) & 3)
        todo.append((num, sb, bits, d, key_of(release, seg, dets[d], obs, d)))
    return versions, known, todo


def measure(item, model):
    """Read one exposure's header window and turn it into a record."""
    num, sb, bits, det, key = item
    try:
        h = pointing_cards(key)
        att = attitude(h, det, model)
        if str(h.get("L2DQAFLG", "Pass")).strip().lower() != "pass":
            bits |= 1 << 15                            # the pipeline's own quality check did not pass
        return (float(h["MJD-OBS"]), att, num, sb, bits)
    except Exception as e:
        return ("error", key, repr(e)[:80])


def pack(seg, release, versions, recs, model):
    recs.sort(key=lambda r: (r[0], r[2], r[3]))
    n, t0 = len(recs), math.floor(recs[0][0])
    buf = b"SXP1" + struct.pack("<I8x", n)
    buf += struct.pack("<%df" % n, *[r[1][0] for r in recs])
    buf += struct.pack("<%df" % n, *[r[1][1] for r in recs])
    buf += struct.pack("<%df" % n, *[r[1][2] for r in recs])
    buf += struct.pack("<%df" % n, *[r[0] - t0 for r in recs])
    buf += struct.pack("<%dH" % n, *[r[2] for r in recs])
    buf += struct.pack("<%dH" % n, *[r[4] for r in recs])
    buf += struct.pack("<%dB" % n, *[r[3] for r in recs])
    images = sum(sum(1 for d in range(6) if (r[4] >> (2 * d)) & 3) for r in recs)
    entry = {"s": seg, "n": n, "t0": t0, "t1": round(recs[-1][0], 5), "r": [release], "v": [versions],
             "m": {release: images}, "c": coverage([r[1] for r in recs], model),
             "h": hashlib.sha1(buf).hexdigest()[:10]}
    unused = sorted(scan_segment.folders.get((release, seg), set()) - set(versions))
    if unused:
        entry["x"] = unused                            # folders that hold nothing the index uses; noted so they are not news tomorrow
    return buf, entry


# ---------------------------------------------------------------- calibration of the focal plane

ORDER = 4
TERMS = [(i, j) for i in range(ORDER + 1) for j in range(ORDER + 1 - i)]

def solve(A, b):
    """Least squares through the normal equations, Gaussian elimination with pivoting."""
    n = len(A[0])
    M = [[sum(r[i] * r[j] for r in A) for j in range(n)] + [sum(r[i] * y for r, y in zip(A, b))] for i in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                M[r] = [a - f * q for a, q in zip(M[r], M[c])]
    return [M[i][n] / M[i][i] for i in range(n)]


def calibrate(exposures):
    """Fit, for each detector, the map from instrument-frame coordinates to detector pixels.

    `exposures` is a list of (release, obs_id) that have all six detectors. The instrument
    frame has its origin at the centre of detector 2 and its x axis toward the centre of
    detector 3. The fixed layout measured here is what lets one attitude per exposure stand in
    for six separate footprints, and lets the page predict which pixel (and so which
    wavelength) a target lands on before it downloads anything.
    """
    grid = [k * 2039.0 / 12 for k in range(13)]
    samples = {d: [] for d in range(1, 7)}             # (X, Y, px, py)
    anchors = {d: [[], [], []] for d in range(1, 7)}
    used, scans = [], {}
    for release, obs in exposures:
        seg = "_".join(obs.split("_")[:2])
        try:
            if (release, seg) not in scans:
                scans[(release, seg)] = scan_segment(release, seg)[0]
            where = scans[(release, seg)][obs]
            hs = {d: image_header(key_of(release, seg, where[d], obs, d)) for d in range(1, 7)}
        except Exception as e:
            log("  skip", obs, repr(e)[:80])
            continue
        mid = {d: pixel_to_vec(hs[d], *ANCHORS[0]) for d in hs}
        z = mid[2]
        x = norm(sub(mid[3], mul(z, dot(mid[3], z))))
        y = cross(z, x)
        to_frame = lambda p: (math.degrees(math.atan(dot(p, x) / dot(p, z))), math.degrees(math.atan(dot(p, y) / dot(p, z))))
        for d in hs:
            for k, (ax, ay) in enumerate(ANCHORS):
                anchors[d][k].append(to_frame(pixel_to_vec(hs[d], ax, ay)))
            for py in grid:
                for px in grid:
                    X, Y = to_frame(pixel_to_vec(hs[d], px, py))
                    samples[d].append((X, Y, px, py))
        used.append([release, obs])
        log("  measured", release, obs)
    mean = lambda pts: [round(sum(p[0] for p in pts) / len(pts), 6), round(sum(p[1] for p in pts) / len(pts), 6)]
    model = {"note": "Instrument frame: origin at the centre of detector 2, x toward the centre of detector 3, y = z cross x. "
                     "Tangent-plane coordinates in degrees; pixels are 0-based. anchors are the frame positions of pixels "
                     + ", ".join(str(a) for a in ANCHORS) + ".",
             "order": ORDER, "scale": 1.75, "exposures": used, "centres": {}, "anchors": {}, "poly": {}, "fit": {}}
    lo = [1e9, 1e9]; hi = [-1e9, -1e9]
    for d in range(1, 7):
        model["anchors"][str(d)] = [mean(a) for a in anchors[d]]
        cx, cy = model["centres"][str(d)] = model["anchors"][str(d)][0]
        rows = [[((X - cx) / 1.75) ** i * ((Y - cy) / 1.75) ** j for i, j in TERMS] for X, Y, _, _ in samples[d]]
        px = solve(rows, [s[2] for s in samples[d]]); py = solve(rows, [s[3] for s in samples[d]])
        model["poly"][str(d)] = {"x": [round(c, 5) for c in px], "y": [round(c, 5) for c in py]}
        err = [math.hypot(sum(a * c for a, c in zip(r, px)) - s[2], sum(a * c for a, c in zip(r, py)) - s[3]) for r, s in zip(rows, samples[d])]
        scatter = max(max(abs(p[0] - cx), abs(p[1] - cy)) for p in anchors[d][0])
        model["fit"][str(d)] = {"rms_px": round(math.sqrt(sum(e * e for e in err) / len(err)), 3), "max_px": round(max(err), 3),
                                "centre_scatter_arcsec": round(3600 * scatter, 2)}
        for X, Y, _, _ in samples[d]:
            lo = [min(lo[0], X), min(lo[1], Y)]; hi = [max(hi[0], X), max(hi[1], Y)]
        log("  detector %d: centre (%+.4f, %+.4f) deg, fit rms %.3f px, worst %.3f px" % (d, cx, cy, model["fit"][str(d)]["rms_px"], model["fit"][str(d)]["max_px"]))
    model["bounds"] = [round(lo[0], 3), round(hi[0], 3), round(lo[1], 3), round(hi[1], 3)]
    release, obs = used[-1]
    seg = "_".join(obs.split("_")[:2])
    model["wave"] = {str(d): wave_table(key_of(release, seg, scans[(release, seg)][obs][d], obs, d)) for d in range(1, 7)}
    model["wave_from"] = [release, obs]
    model["generated"] = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    json.dump(model, open(MODEL, "w"), indent=1)
    log("wrote", MODEL)
    return model


# ---------------------------------------------------------------- the index as a whole

def read_manifest():
    p = os.path.join(OUT, "manifest.json")
    return json.load(open(p)) if os.path.exists(p) else None


def write_manifest(entries, model, complete):
    segs = [entries[s] for s in sorted(entries, key=lambda s: entries[s]["t0"])]
    rel = {}
    for e in segs:
        for r, n in e["m"].items():
            o = rel.setdefault(r, {"images": 0, "t1": 0.0})
            o["images"] += n; o["t1"] = max(o["t1"], e["t1"])
    manifest = {
        "format": 1, "generated": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ"), "complete": complete,
        "cell": CELL, "releases": rel, "exposures": sum(e["n"] for e in segs), "images": sum(v["images"] for v in rel.values()),
        "t0": min(e["t0"] for e in segs), "t1": max(e["t1"] for e in segs),
        "model": {k: model[k] for k in ("order", "scale", "centres", "poly", "bounds", "wave")},
        "segments": segs,
    }
    tmp = os.path.join(OUT, "manifest.json.tmp")
    json.dump(manifest, open(tmp, "w"), separators=(",", ":"))
    os.replace(tmp, os.path.join(OUT, "manifest.json"))
    return manifest


def build(full=False, only=None):
    model = json.load(open(MODEL))
    old = read_manifest()
    entries = {} if old is None else {e["s"]: e for e in old["segments"]}

    releases = bucket_releases()
    owner = {}                                         # segment -> the newest release that has it
    for rel in sorted(releases, key=rank):
        for seg in bucket_segments(rel):
            owner[seg] = rel
    live_model = {k: model[k] for k in ("order", "scale", "centres", "poly", "bounds", "wave")}
    changed = old is None or not old.get("complete") or old.get("model") != live_model
    for seg in [s for s in entries if s not in owner]:  # gone from the bucket
        entries.pop(seg)
        changed = True
        if os.path.exists(os.path.join(OUT, seg + ".bin")):
            os.remove(os.path.join(OUT, seg + ".bin"))
    os.makedirs(OUT, exist_ok=True)
    t_start, fetched, failed = time.time(), 0, 0
    with cf.ThreadPoolExecutor(THREADS) as ex:
        if only:
            todo = sorted(only)
        elif full or old is None:
            todo = sorted(owner)
        else:
            # A daily run lists in full only what can have changed: segments that are new, that
            # moved to a newer release, that gained a processing folder, and the newest few of
            # each release. Everything else waits for the weekly full run.
            def folders(seg):
                return {f.split("/")[3] for f in s3_list("%s/level2/%s/" % (owner[seg], seg))[0]}
            known = [s for s in owner if s in entries and entries[s]["r"] == [owner[s]]]
            moved = {s for s, f in zip(known, ex.map(folders, known)) if not f <= set(entries[s]["v"][0]) | set(entries[s].get("x", []))}
            recent = set()
            for rel in releases:
                recent |= set(sorted(s for s, r in owner.items() if r == rel)[-RECENT:])
            todo = sorted(set(owner) - set(known) | moved | recent)
        log("bucket holds %s; %d week segments, %d to check" % (", ".join(releases), len(owner), len(todo)))
        for c0 in range(0, len(todo), CHUNK):
            chunk = todo[c0:c0 + CHUNK]
            plans = list(ex.map(lambda s: plan_segment(owner[s], s, entries.get(s), full), chunk))
            work = [(seg, item) for seg, (_, _, td) in zip(chunk, plans) for item in td]
            results = list(ex.map(lambda w: measure(w[1], model), work))
            by_seg = collections.defaultdict(list)
            for (seg, _), r in zip(work, results):
                if r[0] == "error":
                    failed += 1
                    if failed <= 10:
                        log("    could not read", r[1], r[2])
                else:
                    by_seg[seg].append(r)
            fetched += len(work)
            for seg, (versions, known, td) in zip(chunk, plans):
                recs = known + by_seg[seg]
                old_e = entries.get(seg)
                if not recs:
                    continue
                if old_e and old_e["r"] != [owner[seg]] and len(recs) < 0.9 * old_e["n"]:
                    log("  %s: %s is still filling up (%d of %d exposures), staying on %s" % (seg, owner[seg], len(recs), old_e["n"], old_e["r"][0]))
                    continue
                if not td and old_e and old_e["n"] == len(recs):
                    continue                           # nothing changed
                buf, entry = pack(seg, owner[seg], versions, recs, model)
                if old_e and old_e["h"] == entry["h"] and old_e["r"] == entry["r"] and old_e["v"] == entry["v"] and old_e.get("x") == entry.get("x"):
                    continue                           # read again and found identical
                with open(os.path.join(OUT, seg + ".bin"), "wb") as f:
                    f.write(buf)
                entries[seg] = entry
                changed = True
            if entries and changed:
                write_manifest(entries, model, complete=False)
            done = min(len(todo), c0 + CHUNK)
            log("  %3d/%d segments  %7d headers read  %5.0f s  (%s)" % (done, len(todo), fetched, time.time() - t_start, chunk[-1]))
    if not changed:                                    # a quiet day: leave the files, and their date, alone
        log("nothing new: %d exposures in %d segments, as before" % (old["exposures"], len(old["segments"])))
        return old
    m = write_manifest(entries, model, complete=not only)
    size = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT))
    log("index: %d exposures, %d images in %d segments, %.1f MB; %s" % (
        m["exposures"], m["images"], len(m["segments"]), size / 1e6,
        ", ".join("%s to MJD %.1f" % (r, v["t1"]) for r, v in sorted(m["releases"].items()))))
    if failed:
        log("%d exposures could not be read and were left out" % failed)
    return m


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--full", action="store_true", help="read every exposure again instead of only the new ones")
    ap.add_argument("--only", nargs="*", metavar="SEGMENT", help="check just these segments")
    ap.add_argument("--calibrate", nargs="*", metavar="RELEASE:OBS_ID", help="refit the focal-plane model")
    a = ap.parse_args()
    if a.calibrate is not None:
        calibrate([tuple(x.split(":")) for x in a.calibrate])
    else:
        build(a.full, a.only)


if __name__ == "__main__":
    main()
