"""Merge the per-process index shards into one index.json, in the canonical target order."""
import sys, os, glob, json, datetime
sys.path.insert(0, 'build')
from make_index import TARGETS, SIZE

OUT = 'data/out'
FINAL = os.path.join(OUT, 'index.json')
ORDER = [t[0] for t in TARGETS]


def main():
    seen = {}
    shards = sorted(glob.glob(os.path.join(OUT, 'index*.json')))
    for path in shards:
        try:
            data = json.load(open(path))
        except Exception as e:
            print("  skip %s (%s)" % (os.path.basename(path), e))
            continue
        for t in data.get('targets', []):
            binp = os.path.join(OUT, t['file'])
            if not os.path.exists(binp):
                print("  skip %s: %s missing" % (t['id'], t['file']))
                continue
            expect = len(t['frames']) * SIZE * SIZE * 2
            if os.path.getsize(binp) != expect:
                print("  skip %s: %s is %d bytes, expected %d"
                      % (t['id'], t['file'], os.path.getsize(binp), expect))
                continue
            if t['id'] not in seen or len(t['frames']) > len(seen[t['id']]['frames']):
                seen[t['id']] = t

    # moving targets lead: a planet crossing the field is the clearest answer to
    # "how does this change over time", so the page should open on one
    def travel(t):
        pts = [f for f in t['frames'] if 'mx' in f]
        return -((pts[-1]['mx'] - pts[0]['mx']) ** 2 + (pts[-1]['my'] - pts[0]['my']) ** 2) if pts else 0
    movers = sorted([t for t in seen.values() if t.get('moving')], key=travel)
    targets = movers + [seen[i] for i in ORDER if i in seen and not seen[i].get('moving')]
    missing = [i for i in ORDER if i not in seen]
    idx = {'generated': datetime.datetime.utcnow().strftime('%Y-%m-%d'),
           'cutout': SIZE, 'pixelScale': 6.15, 'targets': targets}
    json.dump(idx, open(FINAL, 'w'), separators=(',', ':'))

    print("merged %d shards -> %d targets, %d frames"
          % (len(shards), len(targets), sum(len(t['frames']) for t in targets)))
    for t in targets:
        lams = [f['lam'] for f in t['frames']]
        mjds = [f['mjd'] for f in t['frames']]
        print("  %-22s %3d frames  %.2f-%.2f um  %4.0f d  bands %s"
              % (t['name'], len(t['frames']), min(lams), max(lams), max(mjds) - min(mjds),
                 "".join(str(d) for d in sorted(set(f['det'] for f in t['frames'])))))
    if missing:
        print("  still missing: %s" % ", ".join(missing))


if __name__ == '__main__':
    main()
