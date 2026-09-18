"""Read the per-file WCS-WAVE lookup table (wavelength + bandwidth across the detector).

SPHEREx disperses light with a linear variable filter, so the wavelength a pixel records
depends on where the target lands on the detector. Each file carries a small lookup grid;
its dimensions differ per detector (9x9 for the SWIR arrays, up to 13x20 for MWIR), so the
columns are located from TFORM/TDIM rather than assumed.
"""
import sys, re, numpy as np
sys.path.insert(0, 'build')
from fitshdr import hdu_list
from cutout import s3_range

TAIL = 57600  # last 20 FITS blocks: ample for the small WCS-WAVE bintable
_tform = re.compile(r'^\s*(\d*)\s*([A-Z])')
_ITEM = {'J': (4, '>i4'), 'E': (4, '>f4'), 'D': (8, '>f8'), 'I': (2, '>i2')}


def _columns(hdr):
    """[(name, count, itemsize, dtype)] for each bintable column, in file order."""
    cols = []
    for i in range(1, int(hdr.get('TFIELDS', 0)) + 1):
        m = _tform.match(hdr.get('TFORM%d' % i, ''))
        count = int(m.group(1) or 1)
        size, dt = _ITEM[m.group(2)]
        cols.append((hdr.get('TTYPE%d' % i, ''), count, size, dt))
    return cols


def wave_grid(key, filesize):
    """Return (xs, ys, values) where values has shape (len(ys), len(xs), 2): um, um."""
    start = max(0, filesize - TAIL)
    buf = s3_range(key, start, filesize - 1)
    for b in range(len(buf) // 2880):
        off = b * 2880
        if buf[off:off + 20] != b"XTENSION= 'BINTABLE'":
            continue
        h = hdu_list(buf[off:])[0]
        if h.get('truncated') or h['hdr'].get('EXTNAME') != 'WCS-WAVE':
            continue
        d = buf[h['data_start'] + off: h['data_start'] + off + h['data_bytes']]
        got, pos = {}, 0
        for name, count, size, dt in _columns(h['hdr']):
            got[name] = np.frombuffer(d[pos:pos + count * size], dtype=dt)
            pos += count * size
        xs, ys = got['X'].astype(float), got['Y'].astype(float)
        vals = got['VALUES'].astype(float).reshape(len(ys), len(xs), 2)
        return xs, ys, vals
    raise RuntimeError("WCS-WAVE not found in tail of " + key)


def wave_at(xs, ys, vals, px, py):
    """Bilinear interpolation of (wavelength, bandwidth) at 0-based pixel (px, py)."""
    fx, fy = px + 1.0, py + 1.0          # the table is in 1-based FITS coordinates
    i = int(np.clip(np.searchsorted(xs, fx) - 1, 0, len(xs) - 2))
    j = int(np.clip(np.searchsorted(ys, fy) - 1, 0, len(ys) - 2))
    tx = (fx - xs[i]) / (xs[i + 1] - xs[i])
    ty = (fy - ys[j]) / (ys[j + 1] - ys[j])
    out = []
    for c in range(2):
        v = (vals[j, i, c] * (1 - tx) * (1 - ty) + vals[j, i + 1, c] * tx * (1 - ty) +
             vals[j + 1, i, c] * (1 - tx) * ty + vals[j + 1, i + 1, c] * tx * ty)
        out.append(float(v))
    return out
