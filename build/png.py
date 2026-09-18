"""Tiny 8-bit greyscale PNG writer (no PIL dependency)."""
import zlib, struct, numpy as np

def write_gray(path, arr8):
    h, w = arr8.shape
    raw = b"".join(b"\x00" + arr8[y].tobytes() for y in range(h))
    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    open(path, "wb").write(png)

def stretch(a, lo=None, hi=None, p=(1.0, 99.5)):
    f = a[np.isfinite(a)]
    if lo is None: lo = np.percentile(f, p[0])
    if hi is None: hi = np.percentile(f, p[1])
    x = np.clip((np.nan_to_num(a, nan=lo) - lo) / max(hi - lo, 1e-9), 0, 1)
    x = np.arcsinh(x * 10) / np.arcsinh(10.0)
    return (x * 255).astype(np.uint8)
