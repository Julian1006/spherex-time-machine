"""Print the Artifact `files` map for the staged bundle, read back from the built page.

The artifact page lives in app/dist but its data files are served straight out of docs/,
so the two builds never keep separate copies of the 13 MB of frames.
"""
import io, os, re, sys, json

PAGE = 'app/dist/index.html'

src = io.open(PAGE, encoding='utf-8').read()
data = json.loads(re.search(r'const IDX = (\{.*?\});\n', src, re.S).group(1))
files = {t['file']: 'docs/' + t['file'] for t in data['targets']}

print(json.dumps(files))
print("\n%d targets, %.1f MB of frame data, page %.0f KB"
      % (len(files), sum(os.path.getsize(v) for v in files.values()) / 1e6,
         os.path.getsize(PAGE) / 1024), file=sys.stderr)
