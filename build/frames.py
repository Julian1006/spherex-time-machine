"""Build north-up, common-orientation cutouts of a fixed sky position from SPHEREx L2 images.

SPHEREx revisits a target at a different position angle each time, so raw detector
cutouts arrive rotated with respect to one another. Every frame is resampled onto one
shared tangent-plane grid (north up, east left, native 6.15"/px) so the frames blink
against each other cleanly.
"""
import sys, numpy as np
sys.path.insert(0, 'build')
from astropy.io import fits
from astropy.wcs import WCS
from fitshdr import hdu_list
from cutout import s3_range, HDR_PREFIX, fetch_rows

PIXSCALE = 6.15 / 3600.0   # deg/px, SPHEREx native
MARGIN   = 3               # px of slack around the needed input rows

def image_hdu(key):
    buf = s3_range(key, 0, HDR_PREFIX - 1)
    for h in hdu_list(buf):
        if h.get('truncated'): break
        if h.get('extname') == 'IMAGE':
            return h
    raise RuntimeError("no IMAGE extension: " + key)

def out_wcs(ra, dec, size):
    w = WCS(naxis=2)
    w.wcs.crpix = [size/2.0 + 0.5, size/2.0 + 0.5]
    w.wcs.crval = [ra, dec]
    w.wcs.cdelt = [-PIXSCALE, PIXSCALE]     # east left, north up
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    return w

def plan(hdr_cards, ra, dec, size):
    """Map the output grid onto input detector pixels. Returns (sx, sy, affine, resid)."""
    ihdr = fits.Header.fromstring("".join(hdr_cards))
    iw = WCS(ihdr, relax=True)
    ow = out_wcs(ra, dec, size)
    gy, gx = np.mgrid[0:size, 0:size]
    sky = ow.pixel_to_world_values(gx.ravel().astype(float), gy.ravel().astype(float))
    sx, sy = iw.world_to_pixel_values(sky[0], sky[1])
    sx = sx.reshape(size, size); sy = sy.reshape(size, size)
    # least-squares affine approximation, so a browser can reproduce the mapping cheaply
    A = np.column_stack([gx.ravel(), gy.ravel(), np.ones(size*size)])
    cx, *_ = np.linalg.lstsq(A, sx.ravel(), rcond=None)
    cy, *_ = np.linalg.lstsq(A, sy.ravel(), rcond=None)
    resid = float(max(np.abs(A@cx - sx.ravel()).max(), np.abs(A@cy - sy.ravel()).max()))
    return sx, sy, [float(v) for v in list(cx)+list(cy)], resid

def sample(key, data_start, nx, ny, sx, sy):
    """Bilinear-sample the detector at float coords (sx, sy), fetching only the rows needed."""
    y0 = int(np.floor(np.nanmin(sy))) - MARGIN
    y1 = int(np.ceil (np.nanmax(sy))) + MARGIN
    if y0 < 0 or y1 >= ny: return None, 0
    if np.nanmin(sx) < 1 or np.nanmax(sx) >= nx - 1: return None, 0
    nrows = y1 - y0 + 1
    band = fetch_rows(key, data_start, nx, y0, nrows).astype(np.float32)
    x0f = np.floor(sx).astype(int); y0f = np.floor(sy).astype(int)
    fx = (sx - x0f).astype(np.float32); fy = (sy - y0f).astype(np.float32)
    r = y0f - y0
    p00 = band[r,   x0f    ]; p10 = band[r,   x0f + 1]
    p01 = band[r+1, x0f    ]; p11 = band[r+1, x0f + 1]
    out = (p00*(1-fx)*(1-fy) + p10*fx*(1-fy) + p01*(1-fx)*fy + p11*fx*fy)
    return out.astype(np.float32), nrows * nx * 4
