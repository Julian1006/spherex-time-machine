import sys; sys.path.insert(0,'build')
from tap import query

TARGETS = [
 ("North Ecliptic Pole", 270.000, 66.561),
 ("South Ecliptic Pole",  90.000,-66.561),
 ("Orion Nebula M42",     83.822, -5.391),
 ("Andromeda M31",        10.685, 41.269),
 ("Pleiades M45",         56.750, 24.117),
 ("30 Doradus (LMC)",     84.676,-69.101),
 ("Rho Ophiuchi",        246.789,-24.617),
 ("Carina Nebula",       161.265,-59.684),
 ("Galactic Center",     266.417,-29.008),
 ("Ring Nebula M57",     283.396, 33.029),
 ("Helix Nebula",        337.411,-20.837),
 ("Cluster M13",         250.423, 36.460),
]
print("%-22s %6s %8s %8s %s" % ("target","nobs","tmin","tmax","span_d"))
for name, ra, dec in TARGETS:
    try:
        r = query("SELECT COUNT(*) AS n, MIN(t_min) AS a, MAX(t_max) AS b FROM spherex.obscore "
                  "WHERE CONTAINS(POINT('ICRS',%f,%f),s_region)=1" % (ra, dec))
        n = int(r[0]['n']); a = r[0]['a']; b = r[0]['b']
        span = (float(b)-float(a)) if n else 0
        print("%-22s %6d %8.1f %8.1f %6.0f" % (name, n, float(a) if n else 0, float(b) if n else 0, span))
    except Exception as e:
        print("%-22s  FAILED %s" % (name, str(e)[:120]))
