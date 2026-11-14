"""Paint the cover of the page: a sheet of small real frames, a few per target.

The page shows it as a wall of tiles, each one flicking through its own frames. Everything here
is plain Python (no numpy), so the cover can be rebuilt wherever the page can. The sheet is an
8-bit PNG whose palette is the page's own "ember" colours: one byte per pixel, and the browser
needs no script to show it.

    rows    one per target, in the order given by TILES
    columns FRAMES frames of that target, spread over its dates
"""
import json, math, os, struct, zlib

# the first twelve are what most screens show; a very wide one shows all sixteen
TILES = ['m31', 'rosette', 'm1', 'omegacen', 'helix', 'm42',
         'm81', 'tuc47', 'cena', '30dor', 'm104', 'm22',
         'm13', 'm51', 'm5', 'm11']
FRAMES = 4
BLACK, WHITE = 45.0, 99.77          # the page's own default black and white points, in percent
RAMP = [(4, 3, 8), (52, 16, 32), (130, 38, 36), (206, 86, 32), (240, 156, 56), (250, 215, 140), (255, 252, 238)]


def palette():
    out = bytearray()
    for i in range(256):
        t = i / 255 * (len(RAMP) - 1)
        j = min(len(RAMP) - 2, int(t))
        f = t - j
        out += bytes(round(RAMP[j][k] * (1 - f) + RAMP[j + 1][k] * f) for k in range(3))
    return bytes(out)


def stretch(values):
    """One frame of float16 samples, rows south to north -> palette indices, north on top."""
    size = int(round(math.sqrt(len(values))))
    good = sorted(v for v in values if v == v and abs(v) != float('inf'))
    if not good:
        return bytes(len(values)), size
    at = lambda p: good[min(len(good) - 1, max(0, round(p / 100 * (len(good) - 1))))]
    lo, hi = at(BLACK), at(WHITE)
    span = max(1e-9, hi - lo)
    k = 255 / math.asinh(10)
    out = bytearray(len(values))
    for y in range(size):
        src = (size - 1 - y) * size
        for x in range(size):
            v = values[src + x]
            if v == v and abs(v) != float('inf'):
                out[y * size + x] = round(math.asinh(10 * min(1.0, max(0.0, (v - lo) / span))) * k)
    return bytes(out), size


def png(width, height, rows, colours):
    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    raw = b''.join(b'\x00' + r for r in rows)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 3, 0, 0, 0))
            + chunk(b'PLTE', colours) + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def frames_of(target, data_dir, want):
    n = len(target['frames'])
    raw = open(os.path.join(data_dir, 'frames_%s.bin' % target['id']), 'rb').read()
    per = len(raw) // n // 2
    picks = sorted({round(i * (n - 1) / max(1, want - 1)) for i in range(want)})
    return [stretch(struct.unpack('<%de' % per, raw[k * per * 2:(k + 1) * per * 2])) for k in picks]


def build(index, data_dir, out_path, tiles=TILES, frames=FRAMES):
    """Write the sheet and return what the page needs to know about it."""
    by_id = {t['id']: t for t in index['targets']}
    chosen = [by_id[i] for i in tiles if i in by_id]
    rows, size = [], index['cutout']
    for t in chosen:
        cells = frames_of(t, data_dir, frames)
        while len(cells) < frames:
            cells.append(cells[-1])
        for y in range(size):
            rows.append(b''.join(c[0][y * size:(y + 1) * size] for c in cells))
    open(out_path, 'wb').write(png(frames * size, len(chosen) * size, rows, palette()))
    return {'file': os.path.basename(out_path), 'frames': frames, 'tiles': [t['id'] for t in chosen]}


def sheet(index, data_dir, out_path, columns=8):
    """Every target once, side by side: for choosing which ones go on the cover."""
    size, ts = index['cutout'], index['targets']
    cells = [frames_of(t, data_dir, 3)[1][0] for t in ts]
    blank = bytes(size * size)
    while len(cells) % columns:
        cells.append(blank)
    rows = []
    for r in range(0, len(cells), columns):
        for y in range(size):
            rows.append(b''.join(c[y * size:(y + 1) * size] for c in cells[r:r + columns]))
    open(out_path, 'wb').write(png(columns * size, len(rows), rows, palette()))
    return [t['id'] for t in ts]


if __name__ == '__main__':
    import sys
    idx = json.load(open('data/out/index.json'))
    if len(sys.argv) > 2 and sys.argv[1] == '--sheet':
        print(' '.join(sheet(idx, 'data/out', sys.argv[2])))
    else:
        info = build(idx, 'data/out', 'docs/cover.png')
        print('docs/cover.png  %.0f KB  %d targets x %d frames' % (os.path.getsize('docs/cover.png') / 1024, len(info['tiles']), info['frames']))
