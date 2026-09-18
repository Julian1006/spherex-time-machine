"""Scan the released SPHEREx window for exposures containing a set of solar system bodies."""
import sys, json, os
sys.path.insert(0, 'build')
from moving import find, clusters, describe

BODIES = [
    ("Neptune", "899"),
    ("Uranus", "799"),
    ("Ceres", "1;"),
    ("Vesta", "4;"),
]
T0, T1 = 60789, 61262
OUT = 'data/moving'


def main():
    os.makedirs(OUT, exist_ok=True)
    only = sys.argv[1:]
    for name, cmd in BODIES:
        if only and name not in only:
            continue
        sys.stderr.write("\n=== %s (%s) ===\n" % (name, cmd))
        hits = find(cmd, T0, T1)
        json.dump(hits, open(os.path.join(OUT, name.lower() + '.json'), 'w'))
        print("\n%s: %d exposures contain it" % (name, len(hits)))
        if not hits:
            continue
        runs = describe(clusters(hits))
        print("%-4s %-10s %-9s %-11s %-10s" % ("n", "startMJD", "span_h", "motion_'", "motion_px"))
        for d in runs[:10]:
            print("%-4d %-10.2f %-9.1f %-11.1f %-10.0f"
                  % (d['n'], d['start'], d['span_h'], d['motion_arcmin'], d['motion_px']))
        sys.stdout.flush()


if __name__ == '__main__':
    main()
