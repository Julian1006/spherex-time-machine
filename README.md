# SPHEREx Time Machine

A public web tool for watching the infrared sky change. Pick a patch of sky, press play, and
real NASA SPHEREx survey images blink past in date order — anything that moves or varies
stands out immediately.

Built against the live NASA/IPAC IRSA archive. No mock data anywhere.

---

## What it does

- **Time-lapse playback** of every SPHEREx visit to a target, in date order, over a 15-month baseline.
- **Blink and difference modes** against a pinned reference frame — the classic way to find moving
  or variable objects. A flat field means nothing changed; a black-and-white dot pair means something moved.
- **Click-for-spectrum**: click any source and the tool does quick-look aperture photometry across every
  visit, plotting brightness against wavelength. Because SPHEREx disperses light with a linear variable
  filter, each visit samples a different wavelength — so repeat visits *are* a spectrum.
- **Interactive stretch**: black/white points, asinh/linear/sqrt/log scaling, four colour maps, and an
  optional background flattener for frames with off-axis glow.
- **Band filtering and wavelength sorting**, so you can hold the band fixed for a fair brightness
  comparison, or re-order by wavelength to sweep the spectrum instead of time.
- Live sky coordinates (RA/Dec) and surface brightness in MJy/sr under the cursor.
- **Keep it centred**, for the moving targets: each frame is shifted so the body sits in the
  middle and the stars stream past instead. The same motion seen from the other side.
- **The body's own spectrum**: aperture photometry follows the moving target from frame to
  frame, so a planet's infrared spectrum falls out of the survey's repeat visits.
- Playback speed, and keyboard control (space, arrow keys).

## Provenance on the page

Everything on the page explains itself, with one gesture throughout. Every label in the frame
panel is a button that opens a plain sentence — MJD, resolving power, what a band number means,
what a flagged pixel is — and those survive the redraw the panel does on every frame. Beside each
card heading and each control label sits a small ?, which does the same for the all-sky map, the
three compare modes, the spectrum, and every display and filtering control: what a black point
actually does, why asinh rather than linear, what switching a band off is for.

The jargon stays for people who want it, without shutting anyone else out.

Three sections at the end then walk the panels in reading order — reading a frame, finding your
way around the sky, and the controls — answering what a ? cannot: what each panel is for, which
parts are worth attention, and how to use them together.


The page carries its own provenance. A section at the end states what the data is, with the
figures computed from the index so they cannot drift. The full account of how a frame is made, and
the checks behind it, live in this file rather than on the page.

The frame panel also links to the exact file the frame was cut from, at
`irsa.ipac.caltech.edu/ibe/data/spherex/...`, and the link follows the frame on screen. Anyone
can click through from a pixel on the page to the original 71 MB exposure in NASA's archive.

## The data

| | |
|---|---|
| Mission | NASA SPHEREx (launched 11 March 2025) |
| Products | Level-2 science images, Quick Release 2 and 3 |
| Archive | IRSA at IPAC/Caltech; files mirrored in the public `nasa-irsa-spherex` S3 bucket |
| Coverage used | MJD 60789–61262 (Apr 2025 – Aug 2026) |
| Detector | 2040 × 2040 px, 6.15″/px, 6 arrays spanning 0.75–5.01 µm in 102 channels |
| Units | MJy/sr, straight from the pipeline |

## What's in the bundle

1073 frames across 37 targets, every one a separate SPHEREx exposure. Thirteen open the page;
the other twenty-four fold behind a toggle, and a deep link to one unfolds it.
sky with 30 visits each; three are solar system bodies crossing a fixed field.

| Target | Baseline | Wavelengths sampled | Bands |
|---|---|---|---|
| **Vesta** (moving, 126 px) | 26 h | 0.82–0.97 µm | 1 |
| **Neptune** (moving, 54 px) | 12 d | 0.83–4.72 µm | 1–6 |
| **Uranus** (moving, 24 px) | 10 d | 0.81–4.45 µm | 1, 2, 3, 6 |
| North Ecliptic Pole | 472 d | 0.79–4.82 µm | 1–6 |
| South Ecliptic Pole | 467 d | 0.80–4.93 µm | 1–6 |
| Orion Nebula | 190 d | 0.79–4.93 µm | 1–6 |
| Andromeda Galaxy | 393 d | 0.79–4.61 µm | 1–6 |
| Pleiades | 184 d | 0.79–4.91 µm | 1–6 |
| Tarantula Nebula | 453 d | 0.79–4.82 µm | 1–4, 6 |
| Rho Ophiuchi | 372 d | 0.80–4.76 µm | 1–6 |
| Carina Nebula | 406 d | 0.82–4.90 µm | 1–6 |
| Helix Nebula | 371 d | 0.86–4.81 µm | 1–6 |
| Hercules Cluster | 375 d | 0.85–4.90 µm | 1–6 |

Visits are spaced evenly through the time-ordered list of everything that covers the target, so each
target keeps its full baseline while preserving the real observing pattern — including the pairs of
exposures taken minutes apart within a single visit, where fast-moving objects shift most visibly.

## Watching something move

Ten of the targets are fixed patches of sky. Three are not, and they are the ones that answer
the question the whole tool is about: what does it look like when something moves?

Finding it took a search. A cone query cannot follow a body that travels degrees per day, so the
mission is scanned in twenty-day windows: each window asks IRSA for exposures whose detector
centre falls in a cone covering the body's track over that window, then every returned exposure
is tested against the body's interpolated position at its own timestamp. Neptune turned up in
155 exposures across 27 days of the release.

Picking the right window matters more than picking the body. What has to hold is that the body
crosses a useful fraction of a 13-arcminute cutout during a stretch SPHEREx actually observed —
and the survey revisits a field in bursts hours apart, then not again for months. Fast bodies
work over hours, slow ones over days:

| Body | Apparent motion | Window used | Result |
|---|---|---|---|
| Vesta | 55–310 px/day | 26 hours | 126 px, the full width of the frame |
| Neptune | 1–22 px/day | 12 days | 54 px |
| Uranus | 1–34 px/day | 10 days | 24 px |
| Mars | 260–460 px/day | — | too fast; leaves the frame between any two visits |
| Ceres | 35–240 px/day | — | every covered run moves 345–1072 px |

All frames are cut on one sky-fixed grid centred on the middle of Neptune's track, so the stars
hold still and the planet moves. Each frame also stores Neptune's pixel position, obtained from
Horizons at that exposure's exact timestamp and projected onto the cutout grid — nothing is
fitted to the pixels, so the marker landing on a source is a test rather than a decoration.

It lands. Aperture photometry at each predicted position, against a mirrored control position in
the same frame:

| Body | Frames with a >8σ source where predicted | Median significance | Control |
|---|---|---|---|
| Vesta | 8 / 8 | 1458σ | 0.1σ |
| Neptune | 27 / 30 | 312σ | 0.8σ |
| Uranus | 30 / 30 | 85σ | 0.5σ |

Neptune's three misses are its longest wavelengths, where zodiacal light swamps a planet that is
not especially bright at 5 µm.

## How the frames are produced

The interesting engineering is in the build step.

1. **Find the visits.** An ADQL query against `spherex.obscore` at IRSA's TAP service returns every
   observation whose footprint contains the target. Candidates within 1.42° of the detector centre are
   kept, so the cutout box stays clear of the array edge.

2. **Resolve to files.** `spherex.artifact` maps each observation and detector to its archive path.
   Pipeline version strings vary *within* a single week segment, so paths cannot be constructed by
   hand — the table is queried per week segment and cached on disk.

3. **Read only what is needed.** Each Level-2 file is 71 MB, but the science image is a plain
   uncompressed `float32` array at a known offset. The builder issues HTTP range requests against S3:
   64 KB for the header, then one contiguous band of image rows covering the target — roughly 1.3 MB
   instead of 71 MB. The result is bit-identical to reading the whole file.

4. **Put every frame on one grid.** SPHEREx revisits a target at a different roll angle each time, so
   raw cutouts arrive rotated against each other and will not blink. Every frame is resampled onto one
   shared tangent plane — north up, east left, 6.15″/px — using the full `TAN-SIP` solution from the
   file header. Cross-correlating two independent epochs afterwards gives a 0-pixel offset.

5. **Record the wavelength.** SPHEREx has no filter wheel: wavelength varies across the detector. Each
   file carries a `WCS-WAVE` lookup grid, whose dimensions differ per detector (9×9 for SWIR arrays,
   up to 13×20 for MWIR), so columns are located from `TFORM`/`TDIM` rather than assumed. Bilinear
   interpolation at the target's pixel gives the wavelength and bandwidth for that visit. Values were
   checked against the band limits IRSA publishes in `obscore`, and the implied resolving powers
   (R ≈ 34–125) match the instrument design.

6. **Pack.** Cutouts are stored as little-endian `float16` — two bytes per pixel, full dynamic range,
   NaNs preserved — so the browser can restretch interactively instead of being handed a baked image.

A per-frame affine approximation of the sky-to-detector mapping is also stored (residual ≈ 0.03 px),
which is enough for a browser to reproduce the reprojection and pull wider fields directly from S3.

## Verification

Each stage was checked against something independent rather than assumed:

| Check | Result |
|---|---|
| Range-read cutout vs. reading the whole 71 MB file with astropy | bit-identical |
| Affine approximation vs. the full TAN-SIP mapping | max residual 0.03 px |
| Two epochs of the same field, cross-correlated after reprojection | 0 px offset |
| Interpolated wavelengths vs. the band limits IRSA publishes in `obscore` | all 6 detectors in band |
| Implied resolving power R = λ/Δλ | 34–125, matching the instrument design |
| Brightest NEP source, aperture photometry across 30 visits | smooth stellar SED peaking near 1.4 µm |
| Repeat visits that land on the same wavelength months apart | agree to ~1% |
| Blank-sky control aperture | 0.005 vs 3.6 MJy/sr for the source |
| Moving bodies found where Horizons predicts | 65 of 68 frames above 8σ |
| Same measurement at a mirrored control position | median 0.1–0.8σ |

The last two matter most: independent epochs only agree at the percent level if the reprojection,
the wavelength lookup and the photometry are all correct simultaneously.

An early version of the wavelength lookup read fixed byte offsets into the `WCS-WAVE` table and
returned 0.05 µm for detector 3 — physically impossible for an instrument that starts at 0.75 µm.
The `obscore` band cross-check is what caught it; the grid turned out to be 9×14 there rather than 9×9.

## Running the build

Requires Python 3.11+ with `numpy` and `astropy`.

```bash
python -u build/make_index.py --resume
```

Targets are listed at the top of `build/make_index.py`; adding one needs only a name and coordinates.
The run is resumable and writes `data/out/index.json` after every target. TAP queries are the slow
part, so week-segment lookups are cached under `data/weekcache/`.

Then assemble the page:

```bash
python build/assemble.py data/out/index.json
```

That writes two builds from the one template:

- **`docs/`** — a standalone static site: `index.html` with the frame index inlined, its own
  charset and viewport meta tags, and one `frames_<id>.json` per target. This is what gets served.
- **`app/dist/index.html`** — the same page for a Claude Artifact, whose host supplies those meta
  tags itself. It reads its data files out of `docs/`, so the 13 MB is never duplicated.

To try it locally:

```bash
python -m http.server 8777 --directory docs
```

## Installing it as an app

The web build is a progressive web app: deployed over https (or opened on localhost), Chrome
and Edge offer **Install** in the address bar, and it gets its own icon and window. A service
worker caches the shell on install and each target's frames the first time it is opened, so
after one visit it runs with the network off.

`build/pwa.py` writes `manifest.webmanifest` and `sw.js` into `docs/` and wires them into that
build only. The artifact build never sees them, and `make_usb.py` strips them from the offline
copy: a service worker cannot register on `file://`, and an app cannot be installed from one.

`build/icons.py` draws the icons - a warm infrared source with the track of something that
moved running into it.

## Offline bundle

For a venue with no wifi, or a USB stick:

```bash
python build/make_usb.py
```

That writes `usb/SPHEREx/` with two files to double-click and no dependencies: the deck as a
single self-contained HTML page, and the tool. Typefaces are embedded as data URIs, so the
look survives with no network.

The tool needs one change to run with no server: a `file://` page cannot use `fetch`, so the
frame data also ships as `.js` files that assign into one global and are pulled in with a
script tag. The page picks that path on `file://`, and falls back to it if a fetch fails, so
the same build works from a stick, from a folder, or behind a server.

## Publishing

`docs/` is a plain static directory — no backend, no build step, ~13 MB. It works on any static host.

For GitHub Pages, push this repository and then, under **Settings → Pages**, set the source to the
`main` branch and the `/docs` folder. The site appears at `https://<user>.github.io/<repo>/`.

Netlify Drop, Cloudflare Pages and Vercel all work the same way: point them at `docs/`.

## Layout

```
build/
  make_index.py   target list, visit selection, orchestration
  frames.py       reprojection onto the shared tangent plane
  cutout.py       S3 range reads
  fitshdr.py      streaming FITS header parser (works on a byte prefix)
  waves.py        WCS-WAVE wavelength lookup
  resolve.py      obscore -> S3 key, with disk cache
  tap.py          IRSA TAP client
  ephem.py        JPL Horizons ephemerides, sampled tracks and exact times
  moving.py       windowed search for exposures containing a moving body
  scan_moving.py  run that search over a list of bodies
  make_moving.py  build the sky-fixed sequence with predicted positions
  merge.py        combine per-process index shards into one index.json
  assemble.py     inline the index into the page, stage app/dist
  filesmap.py     print the publish manifest for the staged bundle
  scan.py         check coverage for candidate targets before adding them
  png.py          small PNG writer, for contact sheets when spot-checking frames
app/
  template.html   the tool; single file, no build step, no runtime dependencies
docs/             the built static site, ready to serve
data/out/         reprojected cutout stacks (.bin) and the frame index
```

`data/out/` is committed so the page can be rebuilt without re-downloading ~400 MB from NASA.
`data/weekcache/` is not — it is a cache of IRSA TAP responses and refills itself on the next run.

## Credits

Data: NASA/JPL-Caltech/IPAC. SPHEREx Quick Release products served by
[IRSA](https://irsa.ipac.caltech.edu/Missions/spherex.html).

Spectra shown in the tool are quick-look aperture sums for exploration, not calibrated photometry.
