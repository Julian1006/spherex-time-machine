"""Fetch SPHEREx cutouts from NASA's public S3 bucket using HTTP range requests."""
import urllib.request, numpy as np, sys, io, time
sys.path.insert(0, 'build')
from fitshdr import hdu_list

S3 = "https://nasa-irsa-spherex.s3.amazonaws.com/"
HDR_PREFIX = 65536           # enough for PRIMARY + IMAGE headers

def s3_range(key, start, end, retries=4):
    """Inclusive byte range [start, end]."""
    for i in range(retries):
        try:
            req = urllib.request.Request(S3 + key, headers={"Range": "bytes=%d-%d" % (start, end)})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:
            if i == retries - 1: raise
            time.sleep(1.5 * (i + 1))

def image_meta(key):
    """Return (header_dict, data_start, nx, ny) for the science IMAGE extension."""
    buf = s3_range(key, 0, HDR_PREFIX - 1)
    for h in hdu_list(buf):
        if h.get('truncated'): break
        if h.get('extname') == 'IMAGE':
            return h['hdr'], h['data_start'], h['dims'][0], h['dims'][1]
    raise RuntimeError("no IMAGE extension in first %d bytes of %s" % (HDR_PREFIX, key))

def fetch_rows(key, data_start, nx, row0, nrows):
    """Read a contiguous band of image rows as float32."""
    start = data_start + row0 * nx * 4
    end = start + nrows * nx * 4 - 1
    raw = s3_range(key, start, end)
    return np.frombuffer(raw, dtype='>f4').reshape(nrows, nx)

def fetch_cutout(key, data_start, nx, ny, cx, cy, size):
    """Cutout of `size` x `size` px centred on integer pixel (cx, cy). Returns (array, x0, y0)."""
    half = size // 2
    x0 = int(np.clip(cx - half, 0, nx - size))
    y0 = int(np.clip(cy - half, 0, ny - size))
    band = fetch_rows(key, data_start, nx, y0, size)
    return np.array(band[:, x0:x0 + size], dtype=np.float32), x0, y0
