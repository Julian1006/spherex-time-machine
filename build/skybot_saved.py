"""Known asteroids and comets for every frame of the saved places, asked once, ahead of time.

The page can ask SkyBoT (IMCCE) live, one question per frame, but thirty questions take long
enough in front of an audience to look like a hang. For the saved places the answers never
change, so they are asked here once and kept in docs/sso.json; the page reads that file the
first time the box is ticked and only goes live for places someone types in.

Each frame is asked at its own exposure time, over a circle reaching the corners of the cutout.
Bodies fainter than V 21 are dropped, as the page drops them: SPHEREx would not show them.
Answers are cached in data/skybot_cache.json, so an interrupted run picks up where it stopped.

    python build/skybot_saved.py            ask what is missing, write docs/sso.json
"""
import json, os, sys, time, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor

INDEX = 'data/out/index.json'
CACHE = 'data/skybot_cache.json'
OUT = 'docs/sso.json'
URL = 'https://ssp.imcce.fr/webservices/skybot/api/conesearch.php'
VMAX = 21.0
WORKERS = 6


def sexa(s):
    txt = str(s).strip()
    p = [float(x) for x in txt.split()]
    v = abs(p[0]) + (p[1] if len(p) > 1 else 0) / 60 + (p[2] if len(p) > 2 else 0) / 3600
    return -v if txt.startswith('-') else v


def ask(mjd, ra, dec, radius):
    q = urllib.parse.urlencode({'-ep': '%.6f' % (mjd + 2400000.5), '-ra': '%.6f' % ra, '-dec': '%.6f' % dec,
                                '-rd': '%.4f' % radius, '-mime': 'json', '-output': 'object', '-loc': '500',
                                '-from': 'SPHEREx-Time-Machine'})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(URL + '?' + q, timeout=40) as r:
                text = r.read().decode('utf-8', 'replace')
            try:
                rows = json.loads(text)
            except ValueError:
                return []                                   # an empty patch of sky answers with no JSON at all
            out = []
            for o in rows if isinstance(rows, list) else []:
                try:
                    v = float(o.get('VMag (mag)'))
                except (TypeError, ValueError):
                    continue
                if v > VMAX:
                    continue
                num = o.get('Num')
                name = ('(%s) ' % num if num and num != '-' else '') + (o.get('Name') or '?')
                out.append([round(sexa(o['RA (hms)']) * 15, 6), round(sexa(o['DEC (dms)']), 6), round(v, 1), name])
            return sorted(out, key=lambda x: x[2])
        except Exception:
            time.sleep(2 + 3 * attempt)
    return None


def main():
    idx = json.load(open(INDEX, encoding='utf-8'))
    size, scale = idx.get('cutout', 128), idx.get('pixelScale', 6.15)
    radius = size * scale / 3600 * 0.71 + 0.01             # half the diagonal of the square, in degrees, and a little
    cache = json.load(open(CACHE, encoding='utf-8')) if os.path.exists(CACHE) else {}
    jobs = []
    for t in idx['targets']:
        for f in t['frames']:
            key = '%s|%.5f' % (t['id'], f['mjd'])
            if key not in cache or cache[key] is None:
                jobs.append((key, f['mjd'], t['ra'], t['dec']))
    print('%d frames, %d already asked, %d to ask' % (sum(len(t['frames']) for t in idx['targets']), len(cache), len(jobs)))
    done = 0
    t0 = time.time()
    with ThreadPoolExecutor(WORKERS) as pool:
        for key, rows in zip([j[0] for j in jobs], pool.map(lambda j: ask(j[1], j[2], j[3], radius), jobs)):
            cache[key] = rows
            done += 1
            if done % 50 == 0 or done == len(jobs):
                json.dump(cache, open(CACHE, 'w', encoding='utf-8'), separators=(',', ':'))
                print('  %d / %d   %.0f s' % (done, len(jobs), time.time() - t0))
    out, failed, bodies = {}, 0, 0
    for t in idx['targets']:
        per = {}
        for f in t['frames']:
            rows = cache.get('%s|%.5f' % (t['id'], f['mjd']))
            if rows is None:
                failed += 1
                continue
            per['%.5f' % f['mjd']] = rows
            bodies += len(rows)
        out[t['id']] = per
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    print('%s: %d targets, %d bodies across all frames, %d frames unanswered, %.0f KB'
          % (OUT, len(out), bodies, failed, os.path.getsize(OUT) / 1024))
    if failed:
        sys.exit('some frames got no answer; run again to retry them')


if __name__ == '__main__':
    main()
