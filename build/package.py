"""Package the built site and the whole project for hand-off.

Writes three bundles beside the project:

  spherex-time-machine-site.zip     site files at the zip root - drop the zip straight on Netlify
  spherex-time-machine.zip          site inside one folder - extract, then drag that folder
  spherex-time-machine-project.zip  everything, git history included, ready to push
"""
import os, sys, zipfile

SITE = 'docs'
NAME = 'spherex-time-machine'
SKIP_DIRS = {'__pycache__'}


def write(out, entries):
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for src, arc in entries:
            z.write(src, arcname=arc)
    return os.path.getsize(out)


def main():
    here = os.path.abspath('.')
    parent = os.path.dirname(here)
    site = sorted(os.listdir(SITE))

    flat = [(os.path.join(SITE, f), f) for f in site]
    n1 = write(os.path.join(here, NAME + '-site.zip'), flat)

    nested = [(os.path.join(SITE, f), os.path.join(NAME, f)) for f in site]
    n2 = write(os.path.join(here, NAME + '.zip'), nested)

    project = []
    for dirpath, dirnames, filenames in os.walk(here):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in sorted(filenames):
            if f.endswith('.zip'):
                continue
            full = os.path.join(dirpath, f)
            project.append((full, os.path.join(NAME, os.path.relpath(full, here))))
    n3 = write(os.path.join(parent, NAME + '-project.zip'), project)

    print("%-36s %5.1f MB  (%d files, site at zip root)" % (NAME + '-site.zip', n1/1e6, len(flat)))
    print("%-36s %5.1f MB  (%d files, inside one folder)" % (NAME + '.zip', n2/1e6, len(nested)))
    print("%-36s %5.1f MB  (%d files, full project)" % (NAME + '-project.zip', n3/1e6, len(project)))


if __name__ == '__main__':
    main()
