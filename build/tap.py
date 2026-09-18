import urllib.request, urllib.parse, time, sys, io, csv
TAP = "https://irsa.ipac.caltech.edu/TAP/sync"

def query(adql, retries=3, timeout=600):
    data = urllib.parse.urlencode({
        "QUERY": adql, "FORMAT": "csv", "REQUEST": "doQuery", "LANG": "ADQL"
    }).encode()
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(TAP, data=data)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                txt = r.read().decode('utf-8', 'replace')
            if txt.lstrip().startswith('<'):
                raise RuntimeError("TAP error: " + txt[:400])
            return list(csv.DictReader(io.StringIO(txt)))
        except Exception as e:
            last = e
            sys.stderr.write("  retry %d: %s\n" % (i+1, str(e)[:200]))
            time.sleep(5)
    raise last
