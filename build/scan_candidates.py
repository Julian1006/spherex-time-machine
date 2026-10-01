"""Check coverage for candidate targets before committing to downloading any of them.

One cheap count query each, run in parallel. A target with only a handful of visits, or whose
visits all fall in one night, makes a poor time-lapse however famous the object is.
"""
import sys
sys.path.insert(0, 'build')
from concurrent.futures import ThreadPoolExecutor
from tap import query

CANDIDATES = [
    # slug, name, ra, dec, blurb
    ("m8", "Lagoon Nebula", 270.904, -24.387,
     "A vast cloud of gas and dust in Sagittarius, lit from inside by newly formed stars."),
    ("m20", "Trifid Nebula", 270.675, -22.972,
     "Three lanes of dark dust cut across a glowing cloud, which is how it got its name."),
    ("m16", "Eagle Nebula", 274.700, -13.807,
     "Home of the Pillars of Creation, columns of cold gas where stars are still condensing."),
    ("m17", "Omega Nebula", 275.196, -16.172,
     "One of the brightest and most massive star-forming regions in the galaxy."),
    ("rosette", "Rosette Nebula", 97.950, 4.950,
     "A ring of gas around a young cluster whose winds have blown out the middle."),
    ("california", "California Nebula", 60.000, 36.417,
     "A long ribbon of hydrogen in Perseus, faint to the eye but prominent in the infrared."),
    ("horsehead", "Horsehead Nebula", 85.246, -2.458,
     "A pillar of dark dust silhouetted against glowing gas, beside the belt of Orion."),
    ("catseye", "Cat's Eye Nebula", 269.639, 66.633,
     "A dying star shedding concentric shells of gas, close to the northern deep field."),
    ("m27", "Dumbbell Nebula", 299.902, 22.721,
     "A bright planetary nebula, the cast-off atmosphere of a star like the Sun."),
    ("m1", "Crab Nebula", 83.633, 22.015,
     "The wreckage of a star that exploded in 1054, still expanding today."),
    ("m57", "Ring Nebula", 283.396, 33.029,
     "A near-perfect ring of glowing gas around a white dwarf in Lyra."),
    ("omegacen", "Omega Centauri", 201.697, -47.480,
     "The largest globular cluster in the galaxy, some ten million stars bound together."),
    ("tuc47", "47 Tucanae", 6.024, -72.081,
     "A dense southern globular cluster, second only to Omega Centauri in brightness."),
    ("m22", "Cluster M22", 279.100, -23.905,
     "One of the nearest globular clusters, seen through the crowded fields of Sagittarius."),
    ("m3", "Cluster M3", 205.548, 28.377,
     "Half a million ancient stars, far above the plane of the galaxy."),
    ("m5", "Cluster M5", 229.638, 2.081,
     "One of the oldest globular clusters known, around twelve billion years."),
    ("doublecl", "Double Cluster", 34.750, 57.133,
     "Two young open clusters side by side in Perseus, both only a few million years old."),
    ("m44", "Beehive Cluster", 130.100, 19.667,
     "A loose open cluster near enough to see without a telescope on a dark night."),
    ("m11", "Wild Duck Cluster", 282.766, -6.272,
     "One of the richest open clusters, packed into a small patch of the Milky Way."),
    ("m51", "Whirlpool Galaxy", 202.470, 47.195,
     "A spiral galaxy caught mid-interaction with a smaller companion on its arm."),
    ("m104", "Sombrero Galaxy", 189.998, -11.623,
     "An edge-on spiral with a dust lane so sharp it looks drawn on."),
    ("m81", "Bode's Galaxy", 148.888, 69.065,
     "A grand design spiral, one of the brightest galaxies in the northern sky."),
    ("m82", "Cigar Galaxy", 148.968, 69.680,
     "A starburst galaxy driving plumes of gas out of its own core."),
    ("m33", "Triangulum Galaxy", 23.462, 30.660,
     "The third largest galaxy in the Local Group, seen almost face on."),
    ("cena", "Centaurus A", 201.365, -43.019,
     "A giant elliptical galaxy with a dust lane across it, the remains of a merger."),
    ("smc", "Small Magellanic Cloud", 13.187, -72.829,
     "A dwarf galaxy orbiting the Milky Way, visible from the southern hemisphere."),
]

MIN_VISITS = 120     # obscore rows, counting both detectors a point can land on
MIN_SPAN = 60        # days; a target observed only once over a weekend makes a dull time-lapse


def check(c):
    slug, name, ra, dec, _ = c
    try:
        r = query("SELECT COUNT(*) AS n, MIN(t_min) AS a, MAX(t_max) AS b FROM spherex.obscore "
                  "WHERE CONTAINS(POINT('ICRS',%.5f,%.5f),s_region)=1" % (ra, dec), retries=2)
        n = int(r[0]['n'])
        span = (float(r[0]['b']) - float(r[0]['a'])) if n else 0
        ok = n >= MIN_VISITS and span >= MIN_SPAN
        return (slug, name, n, span, ok)
    except Exception as e:
        return (slug, name, -1, 0, False)


def main():
    with ThreadPoolExecutor(max_workers=6) as ex:
        rows = list(ex.map(check, CANDIDATES))
    print("%-12s %-24s %7s %8s  %s" % ("slug", "name", "visits", "span_d", ""))
    keep = []
    for slug, name, n, span, ok in rows:
        print("%-12s %-24s %7s %8.0f  %s"
              % (slug, name, n if n >= 0 else "ERROR", span, "keep" if ok else "drop"))
        if ok:
            keep.append(slug)
    print("\n%d of %d usable: %s" % (len(keep), len(rows), " ".join(keep)))


if __name__ == '__main__':
    main()
