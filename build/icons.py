"""Generate the app icons: a bright infrared source with a track running through it.

No image library here, so the PNGs are written by hand (RGBA, colour type 6). The artwork is
the tool's own idea in miniature - a warm point source on a dark field, and the faint diagonal
of something that moved between visits.
"""
import io, os, zlib, struct, math
import numpy as np

OUT = 'docs'
BG = (14, 13, 12)
TRACK = (126, 200, 227)
# the glow runs out through the detector's own band colours
GLOW = [(1.00, (255, 252, 240)), (0.55, (244, 228, 188)), (0.30, (224, 138, 71)),
        (0.14, (179, 64, 43)), (0.0, BG)]


def write_rgba(path, arr):
    h, w, _ = arr.shape
    raw = b"".join(b"\x00" + arr[y].tobytes() for y in range(h))
    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    io.open(path, 'wb').write(png)


def ramp(t):
    """Colour of the glow at normalised brightness t."""
    stops = sorted(GLOW, key=lambda s: s[0])
    for i in range(len(stops) - 1):
        a, b = stops[i], stops[i + 1]
        if a[0] <= t <= b[0]:
            f = 0.0 if b[0] == a[0] else (t - a[0]) / (b[0] - a[0])
            return [a[1][k] * (1 - f) + b[1][k] * f for k in range(3)]
    return list(stops[-1][1])


def draw(n):
    img = np.zeros((n, n, 4), dtype=np.float64)
    img[..., :3] = BG
    img[..., 3] = 255
    yy, xx = np.mgrid[0:n, 0:n].astype(float)

    # the track: three faint dots on a diagonal, the thing that moved
    for fx, fy, a in [(0.17, 0.85, .50), (0.26, 0.74, .68), (0.35, 0.63, .88)]:
        r = np.hypot(xx - fx * n, yy - fy * n) / (n * 0.042)
        w = np.clip(1 - r * r, 0, 1) ** 1.2 * a
        for c in range(3):
            img[..., c] = img[..., c] * (1 - w) + TRACK[c] * w

    # the source itself, a soft core with a wide halo
    r = np.hypot(xx - n / 2, yy - n / 2) / (n * 0.165)
    t = np.clip(np.exp(-r * r * 2.2), 0, 1)
    lut = np.array([ramp(v / 255.0) for v in range(256)])
    idx = np.clip((t * 255).astype(int), 0, 255)
    glow = lut[idx]
    w = np.clip(t * 2.3, 0, 1)[..., None]
    img[..., :3] = img[..., :3] * (1 - w) + glow * w

    # four short diffraction spikes, so it reads as a star and not a blob
    for ang in (0, math.pi / 2):
        dx, dy = math.cos(ang), math.sin(ang)
        along = (xx - n / 2) * dx + (yy - n / 2) * dy
        across = abs(-(xx - n / 2) * dy + (yy - n / 2) * dx)
        s = np.clip(1 - abs(along) / (n * 0.40), 0, 1) ** 1.6 * np.clip(1 - across / (n * 0.009), 0, 1)
        s = (s * 0.95)[..., None]
        img[..., :3] = img[..., :3] * (1 - s) + np.array([255, 250, 238]) * s

    return np.clip(img, 0, 255).astype(np.uint8)


def main():
    os.makedirs(OUT, exist_ok=True)
    for n in (192, 512):
        p = os.path.join(OUT, 'icon-%d.png' % n)
        write_rgba(p, draw(n))
        print("  %-22s %6.0f KB" % (os.path.basename(p), os.path.getsize(p) / 1024))


if __name__ == '__main__':
    main()
