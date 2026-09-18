"""Minimal streaming FITS header parser - no astropy, works on a byte prefix."""
import sys

def parse_cards(block_bytes):
    cards = []
    for i in range(len(block_bytes)//80):
        c = block_bytes[i*80:(i+1)*80].decode('ascii', 'replace')
        if c.startswith('END '):
            return cards, True
        cards.append(c)
    return cards, False

def header_dict(cards):
    d = {}
    for c in cards:
        key = c[:8].strip()
        if key == 'HIERARCH' or '=' not in c[8:10]:
            continue
        val = c[10:]
        # strip inline comment outside quotes
        if val.lstrip().startswith("'"):
            end = val.index("'", val.index("'")+1)
            v = val[val.index("'")+1:end].strip()
        else:
            v = val.split('/')[0].strip()
        d[key] = v
    return d

def hdu_list(buf):
    """Yield dicts describing each HDU found in buf. Stops when buf runs out."""
    off = 0
    idx = 0
    out = []
    while off + 2880 <= len(buf):
        cards = []
        hstart = off
        complete = False
        while off + 2880 <= len(buf):
            blk = buf[off:off+2880]; off += 2880
            cs, done = parse_cards(blk)
            cards += cs
            if done:
                complete = True
                break
        if not complete:
            out.append({'index': idx, 'truncated': True, 'header_start': hstart})
            break
        hend = off
        d = header_dict(cards)
        naxis = int(d.get('NAXIS', 0))
        dims = [int(d.get('NAXIS%d' % i, 0)) for i in range(1, naxis+1)]
        npix = 1
        for n in dims: npix *= n
        if naxis == 0: npix = 0
        bitpix = int(d.get('BITPIX', 8))
        nbytes = npix * abs(bitpix)//8 + int(d.get('PCOUNT', 0) or 0)
        pad = ((nbytes + 2879)//2880)*2880
        out.append({'index': idx, 'extname': d.get('EXTNAME', '' if idx else 'PRIMARY'),
                    'xtension': d.get('XTENSION',''), 'bitpix': bitpix, 'dims': dims,
                    'header_start': hstart, 'header_end': hend, 'data_start': hend,
                    'data_bytes': nbytes, 'next_hdu': hend + pad, 'ncards': len(cards),
                    'hdr': d, 'cards': cards})
        off = hend + pad
        idx += 1
        if off > len(buf): break
    return out

if __name__ == '__main__':
    buf = open(sys.argv[1],'rb').read()
    for h in hdu_list(buf):
        if h.get('truncated'):
            print("HDU %d: TRUNCATED (header starts @ %d)" % (h['index'], h['header_start'])); break
        print("HDU %-2d %-12s %-9s bitpix=%-4d dims=%-14s hdr=[%d..%d] data=[%d..%d] cards=%d"
              % (h['index'], h['extname'], h['xtension'], h['bitpix'], str(h['dims']),
                 h['header_start'], h['header_end'], h['data_start'], h['data_start']+h['data_bytes'], h['ncards']))
