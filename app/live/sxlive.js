/* sxlive.js — read SPHEREx Level-2 images straight from NASA's public bucket, in the browser.

   There is no server behind this. The bucket (nasa-irsa-spherex on AWS) answers HTTP range
   requests and sends CORS headers, so a page can ask for the few hundred kilobytes it needs
   out of a 65 MB exposure. Everything else happens here: reading the FITS headers, the
   TAN-SIP astrometry carried by each file, and the resampling onto a north-up grid.

   It is a port of build/fitshdr.py, build/frames.py and build/waves.py, and test.html checks
   that it reproduces the frames those scripts made, pixel for pixel. */
(function (root) {
  "use strict";

  const S3 = "https://nasa-irsa-spherex.s3.amazonaws.com/";
  const BLOCK = 2880;                 // FITS files are made of 2880-byte blocks
  const HDR_PREFIX = 65536;           // enough for the PRIMARY and IMAGE headers
  const PIXSCALE = 6.15 / 3600;       // degrees per pixel, SPHEREx native
  const MARGIN = 3;                   // rows of slack around the rows a cutout needs
  const D2R = Math.PI / 180;

  const stats = { bytes: 0, requests: 0 };

  /* ---------- transport ---------- */

  const TIMEOUT = 60000;              // a request that has not finished in a minute has stalled

  /** One GET, read to the end. A few attempts, and a stalled request is dropped rather than
      waited on for ever. `signal` lets the caller cancel; a missing file is reported at once. */
  async function get(url, headers, signal, asText) {
    let last;
    for (let i = 0; i < 4; i++) {
      const ac = new AbortController(), timer = setTimeout(() => ac.abort(), TIMEOUT), stop = () => ac.abort();
      if (signal) { if (signal.aborted) ac.abort(); else signal.addEventListener("abort", stop, { once: true }); }
      try {
        const r = await fetch(url, { headers: headers || {}, signal: ac.signal });
        if (r.status === 404) { const e = new Error("not found: " + url); e.notFound = true; throw e; }
        if (!r.ok) throw new Error("HTTP " + r.status + " for " + url);
        const body = asText ? await r.text() : await r.arrayBuffer();
        stats.bytes += asText ? body.length : body.byteLength; stats.requests++;
        return body;
      } catch (e) {
        if (e.notFound || (signal && signal.aborted)) throw e;
        last = e;
        await new Promise(res => setTimeout(res, 400 * (i + 1)));
      } finally {
        clearTimeout(timer);
        if (signal) signal.removeEventListener("abort", stop);
      }
    }
    throw last;
  }

  /** Inclusive byte range [start, end] of one object in the bucket. */
  const range = (key, start, end, signal) => get(S3 + key, { Range: "bytes=" + start + "-" + end }, signal);

  /** The last n bytes of an object. */
  const tail = (key, n, signal) => get(S3 + key, { Range: "bytes=-" + n }, signal);

  /** Sub-folders and files directly under a prefix (one page, up to 1000 entries). */
  async function list(prefix, signal) {
    const xml = await get(S3 + "?list-type=2&delimiter=/&prefix=" + encodeURIComponent(prefix), null, signal, true);
    const grab = re => Array.from(xml.matchAll(re), m => m[1]);
    return {
      folders: grab(/<CommonPrefixes><Prefix>([^<]*)<\/Prefix>/g),
      files: grab(/<Key>([^<]*)<\/Key>/g),
      truncated: xml.indexOf("<IsTruncated>true") >= 0
    };
  }

  /* ---------- FITS headers ---------- */

  const ascii = new TextDecoder("ascii");

  function cardValue(text) {
    const t = text.replace(/^\s+/, "");
    if (t[0] === "'") {                                   // quoted string; '' is an escaped quote
      let out = "", i = 1;
      for (; i < t.length; i++) {
        if (t[i] === "'") { if (t[i + 1] === "'") { out += "'"; i++; } else break; }
        else out += t[i];
      }
      return out.replace(/\s+$/, "");
    }
    const v = t.split("/")[0].trim();
    if (v === "T") return true;
    if (v === "F") return false;
    if (v === "") return null;
    const n = Number(v.replace(/[dD]/, "E"));
    return Number.isNaN(n) ? v : n;
  }

  /** Parse one header starting at byte `off`. Returns null if it runs past the buffer. */
  function parseHeader(u8, off) {
    const h = {};
    let p = off, done = false, ncards = 0;
    while (!done) {
      if (p + BLOCK > u8.length) return null;
      for (let i = 0; i < 36; i++) {
        const card = ascii.decode(u8.subarray(p + i * 80, p + i * 80 + 80));
        if (card.slice(0, 8) === "END     ") { done = true; break; }
        ncards++;
        if (card.slice(0, 9) === "HIERARCH ") {            // HIERARCH LONG NAME = value / comment
          const eq = card.indexOf("=");
          if (eq > 0) h[card.slice(9, eq).trim()] = cardValue(card.slice(eq + 1));
        } else if (card.slice(8, 10) === "= ") {
          h[card.slice(0, 8).trim()] = cardValue(card.slice(10));
        }
      }
      p += BLOCK;
    }
    const naxis = h.NAXIS || 0;
    let npix = naxis ? 1 : 0;
    for (let i = 1; i <= naxis; i++) npix *= h["NAXIS" + i];
    const dataBytes = Math.abs(h.BITPIX || 8) / 8 * (h.GCOUNT || 1) * ((h.PCOUNT || 0) + npix);
    return {
      h: h, ncards: ncards, headerStart: off, dataStart: p, dataBytes: dataBytes,
      next: p + Math.ceil(dataBytes / BLOCK) * BLOCK,
      name: h.EXTNAME || (off === 0 ? "PRIMARY" : "")
    };
  }

  /* ---------- astrometry: gnomonic projection plus SIP distortion ---------- */

  /** East, north and centre unit vectors of the tangent plane at (ra, dec), in degrees. */
  function frame(ra, dec) {
    const a = ra * D2R, d = dec * D2R, sa = Math.sin(a), ca = Math.cos(a), sd = Math.sin(d), cd = Math.cos(d);
    return { e: [-sa, ca, 0], n: [-sd * ca, -sd * sa, cd], c: [cd * ca, cd * sa, sd] };
  }

  function unit(ra, dec) {
    const a = ra * D2R, d = dec * D2R, cd = Math.cos(d);
    return [cd * Math.cos(a), cd * Math.sin(a), Math.sin(d)];
  }

  function sipTable(h, name) {
    const order = h[name + "_ORDER"];
    if (order === undefined) return null;
    const terms = [];
    for (let p = 0; p <= order; p++) for (let q = 0; p + q <= order; q++) {
      const c = h[name + "_" + p + "_" + q];
      if (c) terms.push([p, q, c]);
    }
    return terms;
  }

  function sipEval(terms, u, v) {
    let s = 0;
    for (let i = 0; i < terms.length; i++) {
      const t = terms[i];
      s += t[2] * Math.pow(u, t[0]) * Math.pow(v, t[1]);
    }
    return s;
  }

  /** Build the sky <-> pixel mapping from an IMAGE header. Pixels are 0-based throughout. */
  function makeWcs(h) {
    if (String(h.CTYPE1).indexOf("TAN") < 0) throw new Error("unsupported projection " + h.CTYPE1);
    const d1 = h.CDELT1 === undefined ? 1 : h.CDELT1, d2 = h.CDELT2 === undefined ? 1 : h.CDELT2;
    let c11, c12, c21, c22;
    if (h.CD1_1 !== undefined) {
      c11 = h.CD1_1; c12 = h.CD1_2 || 0; c21 = h.CD2_1 || 0; c22 = h.CD2_2;
    } else {
      c11 = d1 * (h.PC1_1 === undefined ? 1 : h.PC1_1); c12 = d1 * (h.PC1_2 || 0);
      c21 = d2 * (h.PC2_1 || 0); c22 = d2 * (h.PC2_2 === undefined ? 1 : h.PC2_2);
    }
    const det = c11 * c22 - c12 * c21;
    const i11 = c22 / det, i12 = -c12 / det, i21 = -c21 / det, i22 = c11 / det;
    const A = sipTable(h, "A") || [], B = sipTable(h, "B") || [];
    const AP = sipTable(h, "AP"), BP = sipTable(h, "BP");
    const f = frame(h.CRVAL1, h.CRVAL2);
    const px = h.CRPIX1 - 1, py = h.CRPIX2 - 1;

    /** Unit vector on the sky -> [x, y] detector pixel, or null if behind the tangent plane. */
    function vecToPixel(p) {
      const den = p[0] * f.c[0] + p[1] * f.c[1] + p[2] * f.c[2];
      if (den <= 0) return null;
      const x = (p[0] * f.e[0] + p[1] * f.e[1] + p[2] * f.e[2]) / den / D2R;
      const y = (p[0] * f.n[0] + p[1] * f.n[1] + p[2] * f.n[2]) / den / D2R;
      const U = i11 * x + i12 * y, V = i21 * x + i22 * y;
      // the header's own inverse polynomial gives a starting point; the forward one is then
      // inverted exactly, which is what astropy does and why the two agree
      let u = U, v = V;
      if (AP && BP) { u = U + sipEval(AP, U, V); v = V + sipEval(BP, U, V); }
      for (let k = 0; k < 6; k++) {
        const du = U - (u + sipEval(A, u, v)), dv = V - (v + sipEval(B, u, v));
        u += du; v += dv;
        if (Math.abs(du) < 1e-9 && Math.abs(dv) < 1e-9) break;
      }
      return [u + px, v + py];
    }

    function pixelToSky(x, y) {
      const u = x - px, v = y - py;
      const U = u + sipEval(A, u, v), V = v + sipEval(B, u, v);
      const xi = (c11 * U + c12 * V) * D2R, eta = (c21 * U + c22 * V) * D2R;
      const p = [f.c[0] + xi * f.e[0] + eta * f.n[0], f.c[1] + xi * f.e[1] + eta * f.n[1], f.c[2] + xi * f.e[2] + eta * f.n[2]];
      const r = Math.hypot(p[0], p[1], p[2]);
      let ra = Math.atan2(p[1], p[0]) / D2R; if (ra < 0) ra += 360;
      return [ra, Math.asin(p[2] / r) / D2R];
    }

    return {
      vecToPixel: vecToPixel,
      skyToPixel: (ra, dec) => vecToPixel(unit(ra, dec)),
      pixelToSky: pixelToSky
    };
  }

  /* ---------- one exposure ---------- */

  /** Read the headers of one Level-2 file. One request of 64 KB. */
  async function openImage(key, signal) {
    const u8 = new Uint8Array(await range(key, 0, HDR_PREFIX - 1, signal));
    let off = 0, primary = null;
    for (let i = 0; i < 4; i++) {
      const hdu = parseHeader(u8, off);
      if (!hdu) break;
      if (i === 0) primary = hdu.h;
      if (hdu.name === "IMAGE") {
        const h = hdu.h;
        return {
          key: key, h: h, primary: primary, dataStart: hdu.dataStart, nx: h.NAXIS1, ny: h.NAXIS2,
          flagsHeaderAt: hdu.next, wcs: makeWcs(h), det: h.DETECTOR, obs: h.OBSID,
          mjd: h["MJD-AVG"] !== undefined ? h["MJD-AVG"] : h["MJD-OBS"], date: h["DATE-AVG"] || h["DATE-OBS"],
          exposure: h.XPOSURE, unit: h.BUNIT,
          quality: {                                       // exposure-level contamination notes
            l1: h.L1DQAFLG, l2: h.L2DQAFLG, fineAstrometry: h.FINAST === undefined ? null : h.FINAST === 0,
            aurora: h.AURORA_CONT, shuttleGlow: h.SHUTTLE_GLOW_CONT, heAirglow: h.HE_AIRGLOW_CONT,
            sourcePercent: h.PXSRCMSK, psfFwhm: h.PSF_FWHM
          }
        };
      }
      off = hdu.next;
    }
    throw new Error("no IMAGE extension in the first " + HDR_PREFIX + " bytes of " + key);
  }

  /** Where each pixel of a north-up `size` x `size` grid centred on (ra, dec) falls on the detector.
      `scale` is the output pixel size in degrees. With `ss` > 1 every output pixel is sampled
      at ss x ss points, which cutout() then averages: that is how a field wider than the
      native sampling is binned down instead of skipping detector pixels. */
  function plan(wcs, ra, dec, size, scale, ss) {
    ss = ss || 1;
    const f = frame(ra, dec), step = (scale || PIXSCALE) * D2R, half = (size - 1) / 2;
    const sx = new Float64Array(size * size * ss * ss), sy = new Float64Array(sx.length);
    let minx = Infinity, maxx = -Infinity, miny = Infinity, maxy = -Infinity, ok = true, k = 0;
    for (let gy = 0; gy < size; gy++) for (let gx = 0; gx < size; gx++) {
      for (let b = 0; b < ss; b++) for (let a = 0; a < ss; a++, k++) {
        const xi = -(gx - half + (a + 0.5) / ss - 0.5) * step;       // east is to the left
        const eta = (gy - half + (b + 0.5) / ss - 0.5) * step;
        const p = [f.c[0] + xi * f.e[0] + eta * f.n[0], f.c[1] + xi * f.e[1] + eta * f.n[1], f.c[2] + xi * f.e[2] + eta * f.n[2]];
        const q = wcs.vecToPixel(p);
        if (!q) { ok = false; sx[k] = sy[k] = NaN; continue; }
        sx[k] = q[0]; sy[k] = q[1];
        if (q[0] < minx) minx = q[0]; if (q[0] > maxx) maxx = q[0];
        if (q[1] < miny) miny = q[1]; if (q[1] > maxy) maxy = q[1];
      }
    }
    return { sx: sx, sy: sy, minx: minx, maxx: maxx, miny: miny, maxy: maxy, ok: ok, size: size, ss: ss };
  }

  /** True if the whole cutout lies on the detector. Costs nothing: no request is made. */
  function fits(img, pl) {
    if (!pl.ok) return false;
    const y0 = Math.floor(pl.miny) - MARGIN, y1 = Math.ceil(pl.maxy) + MARGIN;
    return y0 >= 0 && y1 < img.ny && pl.minx >= 1 && pl.maxx < img.nx - 1;
  }

  /** Fetch only the detector rows a cutout needs and resample them (bilinear). One request. */
  async function cutout(img, ra, dec, size, opts) {
    opts = opts || {};
    const pl = opts.plan || plan(img.wcs, ra, dec, size, opts.scale, opts.ss);
    if (!fits(img, pl)) return null;
    const nx = img.nx, y0 = Math.floor(pl.miny) - MARGIN, y1 = Math.ceil(pl.maxy) + MARGIN, nrows = y1 - y0 + 1;
    const start = (opts.dataStart || img.dataStart) + y0 * nx * 4;
    const buf = await range(img.key, start, start + nrows * nx * 4 - 1, opts.signal);
    const dv = new DataView(buf), out = new Float32Array(size * size), per = pl.ss * pl.ss;
    let finite = 0;
    for (let k = 0, j = 0; k < out.length; k++) {
      let sum = 0, got = 0;
      for (let q = 0; q < per; q++, j++) {
        const x = pl.sx[j], y = pl.sy[j], xf = Math.floor(x), yf = Math.floor(y), fx = x - xf, fy = y - yf;
        const o = ((yf - y0) * nx + xf) * 4;
        const p00 = dv.getFloat32(o, false), p10 = dv.getFloat32(o + 4, false);
        const p01 = dv.getFloat32(o + nx * 4, false), p11 = dv.getFloat32(o + nx * 4 + 4, false);
        const v = p00 * (1 - fx) * (1 - fy) + p10 * fx * (1 - fy) + p01 * (1 - fx) * fy + p11 * fx * fy;
        if (per === 1) { sum = v; got = 1; }
        else if (v === v && v !== Infinity && v !== -Infinity) { sum += v; got++; }
      }
      const v = got ? sum / got : NaN;
      out[k] = v;
      if (v === v && v !== Infinity && v !== -Infinity) finite++;
    }
    const mid = (Math.floor(size / 2) * size + Math.floor(size / 2)) * per;
    const t = img.wcs.skyToPixel(ra, dec);
    return { data: out, size: size, finite: finite / out.length, bytes: buf.byteLength, rows: nrows,
             detX: pl.sx[mid], detY: pl.sy[mid], tx: t ? t[0] : NaN, ty: t ? t[1] : NaN };
  }

  /* ---------- pixel flags ----------

     Every Level-2 file carries a FLAGS layer after the image: one 32-bit number per detector
     pixel, each bit a warning from the pipeline (a cosmic-ray hit, a dead pixel, a ghost...).
     Older releases store it as a plain image. Newer ones compress it row by row (FITS tile
     compression, RICE_1), so a row has to be found through a small table and unpacked here. */

  const NONZERO = new Uint8Array(256);                    // how many bits a byte needs
  for (let i = 1; i < 256; i++) NONZERO[i] = 32 - Math.clz32(i);

  /** Unpack one Rice-compressed tile of 32-bit integers: n pixels from c[p...] into out[o...].
      A port of fits_rdecomp from CFITSIO. */
  function unrice(c, p, n, nblock, out, o) {
    const fsbits = 5, fsmax = 25, bbits = 32;
    let last = (c[p] << 24) | (c[p + 1] << 16) | (c[p + 2] << 8) | c[p + 3];
    p += 4;
    let b = c[p++], nbits = 8;
    for (let i = 0; i < n;) {
      nbits -= fsbits;
      while (nbits < 0) { b = ((b << 8) | c[p++]) >>> 0; nbits += 8; }
      const fs = (b >>> nbits) - 1;
      b &= (1 << nbits) - 1;
      const imax = Math.min(n, i + nblock);
      if (fs < 0) {                                       // every pixel of the block repeats the last one
        for (; i < imax; i++) out[o + i] = last;
      } else if (fs === fsmax) {                          // too noisy to code: the differences are stored whole
        for (; i < imax; i++) {
          let k = bbits - nbits, diff = k < 32 ? b << k : 0;
          for (k -= 8; k >= 0; k -= 8) { b = c[p++]; diff |= b << k; }
          if (nbits > 0) { b = c[p++]; diff |= b >>> (-k); b &= (1 << nbits) - 1; } else b = 0;
          diff >>>= 0;
          last = (((diff & 1) === 0 ? diff >>> 1 : ~(diff >>> 1)) + last) | 0;
          out[o + i] = last;
        }
      } else {                                            // the usual case: a run of zeros, a one, then fs bits
        for (; i < imax; i++) {
          while (b === 0) { nbits += 8; b = c[p++]; }
          const nzero = nbits - NONZERO[b];
          nbits -= nzero + 1;
          b ^= 1 << nbits;
          nbits -= fs;
          while (nbits < 0) { b = ((b << 8) | c[p++]) >>> 0; nbits += 8; }
          const diff = ((nzero << fs) | (b >>> nbits)) >>> 0;
          b &= (1 << nbits) - 1;
          last = (((diff & 1) === 0 ? diff >>> 1 : ~(diff >>> 1)) + last) | 0;
          out[o + i] = last;
        }
      }
    }
    return p;
  }

  /** Where a file's FLAGS layer is and how it is stored. `at` is the byte where its header
      starts, which is where the image data ends. One request of 64 KB. */
  async function openFlags(key, at, signal) {
    let u8 = new Uint8Array(await range(key, at, at + HDR_PREFIX - 1, signal));
    const hdu = parseHeader(u8, 0);
    if (!hdu) throw new Error("the FLAGS header does not fit in " + HDR_PREFIX + " bytes of " + key);
    const h = hdu.h, planes = {};
    for (const k in h) {                                  // what each bit means, by name
      let m = /^MSKN(\d+)$/.exec(k);
      if (m) { planes[String(h[k]).trim()] = +m[1]; continue; }
      m = /^MP_(\w+)$/.exec(k);
      if (m && typeof h[k] === "number") planes[m[1]] = h[k];
    }
    if (String(h.EXTNAME).trim() !== "FLAGS") throw new Error("no FLAGS layer where one was expected in " + key);
    if (String(h.XTENSION).trim() === "IMAGE") {
      if (h.BITPIX !== 32) throw new Error("unexpected FLAGS type in " + key);
      return { key: key, kind: "image", nx: h.NAXIS1, ny: h.NAXIS2, dataStart: at + hdu.dataStart, planes: planes, header: h };
    }
    const wide = /Q/.test(String(h.TFORM1)), width = wide ? 16 : 8, rows = h.NAXIS2;
    let block = 32, bytepix = 4;
    for (let i = 1; h["ZNAME" + i] !== undefined; i++) {
      if (String(h["ZNAME" + i]).trim() === "BLOCKSIZE") block = h["ZVAL" + i];
      if (String(h["ZNAME" + i]).trim() === "BYTEPIX") bytepix = h["ZVAL" + i];
    }
    if (!h.ZIMAGE || String(h.ZCMPTYPE).trim() !== "RICE_1" || h.ZBITPIX !== 32 || bytepix !== 4
        || h.ZTILE1 !== h.ZNAXIS1 || (h.ZTILE2 || 1) !== 1 || h.NAXIS1 !== width || rows !== h.ZNAXIS2) {
      throw new Error("FLAGS are stored in a way this page cannot read in " + key);
    }
    const need = hdu.dataStart + rows * width;
    if (u8.length < need) {                               // the row table ran past the first request
      const more = new Uint8Array(await range(key, at + u8.length, at + need - 1, signal));
      const all = new Uint8Array(need); all.set(u8); all.set(more, u8.length); u8 = all;
    }
    const dv = new DataView(u8.buffer, u8.byteOffset + hdu.dataStart, rows * width);
    const len = new Float64Array(rows), off = new Float64Array(rows);
    for (let r = 0; r < rows; r++) {
      if (wide) { len[r] = dv.getUint32(r * 16, false) * 4294967296 + dv.getUint32(r * 16 + 4, false);
                  off[r] = dv.getUint32(r * 16 + 8, false) * 4294967296 + dv.getUint32(r * 16 + 12, false); }
      else { len[r] = dv.getUint32(r * 8, false); off[r] = dv.getUint32(r * 8 + 4, false); }
    }
    return { key: key, kind: "rice", nx: h.ZNAXIS1, ny: h.ZNAXIS2, len: len, off: off, block: block,
             heap: at + hdu.dataStart + (h.THEAP || rows * width), planes: planes, header: h };
  }

  /** Flags of detector rows y0..y1 inclusive, one Int32 per pixel. One request. */
  async function flagRows(fl, y0, y1, signal) {
    const out = new Int32Array((y1 - y0 + 1) * fl.nx);
    if (fl.kind === "image") {
      const dv = new DataView(await range(fl.key, fl.dataStart + y0 * fl.nx * 4, fl.dataStart + (y1 + 1) * fl.nx * 4 - 1, signal));
      for (let i = 0; i < out.length; i++) out[i] = dv.getInt32(i * 4, false);
      return out;
    }
    let a = Infinity, b = 0;
    for (let y = y0; y <= y1; y++) if (fl.len[y]) { a = Math.min(a, fl.off[y]); b = Math.max(b, fl.off[y] + fl.len[y]); }
    if (b <= a) return out;
    const buf = await range(fl.key, fl.heap + a, fl.heap + b - 1, signal);
    const c = new Uint8Array(buf.byteLength + 8);          // a few zero bytes so a damaged row cannot run off the end
    c.set(new Uint8Array(buf));
    for (let y = y0; y <= y1; y++) if (fl.len[y]) unrice(c, fl.off[y] - a, fl.nx, fl.block, out, (y - y0) * fl.nx);
    return out;
  }

  const SHARE = 0.05;                 // a detector pixel counts once it supplies this much of an output pixel

  /** The flags under each pixel of a cutout laid out by plan(): every detector pixel that takes a
      real part in an output pixel has its bits OR-ed in. One request, plus openFlags' one. */
  async function flagCutout(fl, pl, signal) {
    const y0 = Math.max(0, Math.floor(pl.miny) - 1), y1 = Math.min(fl.ny - 1, Math.ceil(pl.maxy) + 1);
    const rows = await flagRows(fl, y0, y1, signal), nx = fl.nx, per = pl.ss * pl.ss;
    const out = new Int32Array(pl.size * pl.size);
    const at = (x, y) => (x >= 0 && x < nx && y >= y0 && y <= y1) ? rows[(y - y0) * nx + x] : 0;
    for (let k = 0, j = 0; k < out.length; k++) {
      let v = 0;
      for (let q = 0; q < per; q++, j++) {
        const x = pl.sx[j], y = pl.sy[j], xf = Math.floor(x), yf = Math.floor(y), fx = x - xf, fy = y - yf;
        if ((1 - fx) * (1 - fy) > SHARE) v |= at(xf, yf);
        if (fx * (1 - fy) > SHARE) v |= at(xf + 1, yf);
        if ((1 - fx) * fy > SHARE) v |= at(xf, yf + 1);
        if (fx * fy > SHARE) v |= at(xf + 1, yf + 1);
      }
      out[k] = v;
    }
    return out;
  }

  /* ---------- wavelength ---------- */

  const ITEM ={ J: [4, "getInt32"], E: [4, "getFloat32"], D: [8, "getFloat64"], I: [2, "getInt16"] };

  /** The wavelength lookup table at the end of a file: control points X, Y and (um, um) values. */
  async function waveTable(key, signal) {
    const u8 = new Uint8Array(await tail(key, 10 * BLOCK, signal));
    for (let b = Math.floor(u8.length / BLOCK) - 1; b >= 0; b--) {
      const off = u8.length - (Math.floor(u8.length / BLOCK) - b) * BLOCK;
      if (ascii.decode(u8.subarray(off, off + 20)) !== "XTENSION= 'BINTABLE'") continue;
      const hdu = parseHeader(u8, off);
      if (!hdu || hdu.h.EXTNAME !== "WCS-WAVE") continue;
      const dv = new DataView(u8.buffer, u8.byteOffset + hdu.dataStart), got = {};
      let pos = 0;
      for (let i = 1; i <= hdu.h.TFIELDS; i++) {
        const m = /^\s*(\d*)\s*([A-Z])/.exec(hdu.h["TFORM" + i]);
        const count = m[1] ? +m[1] : 1, it = ITEM[m[2]], a = new Float64Array(count);
        for (let k = 0; k < count; k++) a[k] = dv[it[1]](pos + k * it[0], false);
        got[hdu.h["TTYPE" + i]] = a; pos += count * it[0];
      }
      return { xs: got.X, ys: got.Y, values: got.VALUES };
    }
    throw new Error("WCS-WAVE table not found at the end of " + key);
  }

  /** Bilinear interpolation of [wavelength, bandwidth] in microns at a 0-based detector pixel. */
  function waveAt(t, px, py) {
    const fx = px + 1, fy = py + 1, nx = t.xs.length, ny = t.ys.length;   // the table is 1-based
    const find = (a, v) => { let i = 0; while (i < a.length - 2 && a[i + 1] < v) i++; return i; };
    const i = find(t.xs, fx), j = find(t.ys, fy);
    const tx = (fx - t.xs[i]) / (t.xs[i + 1] - t.xs[i]), ty = (fy - t.ys[j]) / (t.ys[j + 1] - t.ys[j]);
    const at = (jj, ii, c) => t.values[(jj * nx + ii) * 2 + c];
    return [0, 1].map(c => at(j, i, c) * (1 - tx) * (1 - ty) + at(j, i + 1, c) * tx * (1 - ty)
      + at(j + 1, i, c) * (1 - tx) * ty + at(j + 1, i + 1, c) * tx * ty);
  }

  /* ---------- finding a file ---------- */

  const versions = new Map();

  /** Processing-version folders of one week segment, in the order worth trying: the main run
      (newest first), then any partial "retry" run, which holds only a few dozen files. Cached. */
  function weekVersions(release, week, signal) {
    const k = release + "/" + week;
    if (!versions.has(k)) {
      const retry = v => /retry/.test(v) ? 1 : 0;
      versions.set(k, list(release + "/level2/" + week + "/", signal)
        .then(r => r.folders.map(f => f.split("/")[3]).sort((a, b) => retry(a) - retry(b) || (a < b ? 1 : -1)))
        .catch(e => { versions.delete(k); throw e; }));
    }
    return versions.get(k);
  }

  const releaseOf = collection => /spherex_([a-z]+\d+)/.exec(collection)[1];     // spherex_dr1_deep -> dr1
  const weekOf = obs => obs.split("_").slice(0, 2).join("_");                    // 2025W19_1B_0116_1 -> 2025W19_1B

  const keyOf = (release, week, ver, obs, det) =>
    release + "/level2/" + week + "/" + ver + "/" + det + "/level2_" + obs + "D" + det + "_spx_" + ver + ".fits";

  /** Open one exposure on one detector when only its observation id is known.
      A week segment can hold more than one processing folder (a main run plus a partial
      "retry" run), so each is tried in turn until the file turns up. */
  async function openExposure(collection, obs, det, signal) {
    const release = releaseOf(collection), week = weekOf(obs);
    const v = await weekVersions(release, week, signal);
    let last = new Error("no files for " + release + " " + week);
    for (let i = 0; i < v.length; i++) {
      try { return await openImage(keyOf(release, week, v[i], obs, det), signal); }
      catch (e) { if (!e.notFound) throw e; last = e; }
    }
    throw last;
  }

  /* ---------- the pointing index: which exposures cover a place ----------

     IRSA's own search cannot be called from a web page, so build/pointing_index.py writes down
     where the telescope pointed in every released exposure. The six detectors keep a fixed
     layout, so one attitude per exposure is enough: the model in the manifest turns it into
     the pixel a target lands on, on each detector, to a fraction of a pixel. */

  const index = { base: "idx/", manifest: null, segments: new Map() };
  const EDGE = 5;                     // pixels kept clear of the detector edge

  async function pool(items, n, fn) {
    let next = 0;
    await Promise.all(Array.from({ length: Math.min(n, items.length) }, async () => {
      while (next < items.length) { const i = next++; await fn(items[i], i); }
    }));
  }

  /** The index manifest. Always asked of the network first: it is rebuilt every day. */
  function manifest(signal) {
    if (!index.manifest) {
      index.manifest = fetch(index.base + "manifest.json", { cache: "no-cache", signal: signal })
        .then(r => { if (!r.ok) throw new Error("index HTTP " + r.status); return r.json(); })
        .then(m => {
          m.terms = [];
          for (let i = 0; i <= m.model.order; i++) for (let j = 0; j <= m.model.order - i; j++) m.terms.push([i, j]);
          return m;
        })
        .catch(e => { index.manifest = null; throw e; });
    }
    return index.manifest;
  }

  function segment(entry, signal) {
    if (!index.segments.has(entry.s)) {
      index.segments.set(entry.s, get(index.base + entry.s + ".bin?v=" + entry.h, null, signal)
        .then(buf => {
          if (ascii.decode(new Uint8Array(buf, 0, 4)) !== "SXP1") throw new Error("not an index file: " + entry.s);
          const n = new DataView(buf).getUint32(4, true);
          let o = 16;
          const f32 = () => { const a = new Float32Array(buf, o, n); o += 4 * n; return a; };
          const u16 = () => { const a = new Uint16Array(buf, o, n); o += 2 * n; return a; };
          return { n: n, ra: f32(), dec: f32(), pa: f32(), t: f32(), num: u16(), bits: u16(), sub: new Uint8Array(buf, o, n) };
        })
        .catch(e => { index.segments.delete(entry.s); throw e; }));
    }
    return index.segments.get(entry.s);
  }

  /** Does this segment come anywhere near (ra, dec)? A coarse test on a 5-degree grid. */
  function covers(entry, ra, dec, cell) {
    if (!entry.bits) { const s = atob(entry.c); entry.bits = Uint8Array.from(s, ch => ch.charCodeAt(0)); }
    const nra = 360 / cell, ndec = 180 / cell;
    const j = Math.min(ndec - 1, Math.max(0, Math.floor((dec + 90) / cell)));
    const i = Math.min(nra - 1, Math.floor((((ra % 360) + 360) % 360) / cell));
    const k = j * nra + i;
    return (entry.bits[k >> 3] >> (k & 7)) & 1;
  }

  /** Detector pixel of instrument-frame point (X, Y) degrees, from the fitted layout. */
  function locate(m, det, X, Y) {
    const c = m.model.centres[det], p = m.model.poly[det], s = m.model.scale;
    const u = (X - c[0]) / s, v = (Y - c[1]) / s;
    let x = 0, y = 0;
    for (let k = 0; k < m.terms.length; k++) {
      const w = Math.pow(u, m.terms[k][0]) * Math.pow(v, m.terms[k][1]);
      x += p.x[k] * w; y += p.y[k] * w;
    }
    return [x, y];
  }

  /** Every released image whose detector holds (ra, dec), oldest first.
      opts.half: half-width of the cutout in degrees; when given, the whole square must fit. */
  async function search(ra, dec, opts) {
    opts = opts || {};
    const m = await manifest(opts.signal), b = m.model.bounds, f = frame(ra, dec);
    const t = opts.half ? Math.tan(opts.half * D2R) : 0;
    const dirs = [[0, 0], [-t, -t], [t, -t], [t, t], [-t, t]].slice(0, t ? 5 : 1).map(q =>
      [f.c[0] + q[0] * f.e[0] + q[1] * f.n[0], f.c[1] + q[0] * f.e[1] + q[1] * f.n[1], f.c[2] + q[0] * f.e[2] + q[1] * f.n[2]]);
    const hits = m.segments.filter(e => covers(e, ra, dec, m.cell)), out = [];
    let done = 0;
    await pool(hits, 8, async e => {
      const s = await segment(e, opts.signal);
      for (let k = 0; k < s.n; k++) {
        const a = s.ra[k] * D2R, d = s.dec[k] * D2R, p = s.pa[k] * D2R;
        const sa = Math.sin(a), ca = Math.cos(a), sd = Math.sin(d), cd = Math.cos(d), sp = Math.sin(p), cp = Math.cos(p);
        const z = [cd * ca, cd * sa, sd], v = dirs[0];
        const vz = v[0] * z[0] + v[1] * z[1] + v[2] * z[2];
        if (vz < 0.98) continue;                                    // more than about 11 degrees off the boresight
        const x = [cp * -sd * ca + sp * -sa, cp * -sd * sa + sp * ca, cp * cd];      // cos(pa) north + sin(pa) east
        const y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]];
        const at = w => { const wz = w[0] * z[0] + w[1] * z[1] + w[2] * z[2];
          return [Math.atan((w[0] * x[0] + w[1] * x[1] + w[2] * x[2]) / wz) / D2R, Math.atan((w[0] * y[0] + w[1] * y[1] + w[2] * y[2]) / wz) / D2R]; };
        const P = at(v);
        if (P[0] < b[0] || P[0] > b[1] || P[1] < b[2] || P[1] > b[3]) continue;
        const bits = s.bits[k];
        for (let det = 1; det <= 6; det++) {
          const vi = (bits >> (2 * (det - 1))) & 3, c = m.model.centres[det];
          if (!vi || Math.abs(P[0] - c[0]) > 1.9 || Math.abs(P[1] - c[1]) > 1.9) continue;
          let ok = true, px = 0, py = 0;
          for (let q = 0; q < dirs.length && ok; q++) {
            const Q = q ? at(dirs[q]) : P, xy = locate(m, det, Q[0], Q[1]);
            if (!q) { px = xy[0]; py = xy[1]; }
            ok = xy[0] >= EDGE && xy[0] <= 2039 - EDGE && xy[1] >= EDGE && xy[1] <= 2039 - EDGE;
          }
          if (!ok) continue;
          const ri = (bits >> 12) & 3, release = e.r[ri], ver = e.v[ri][vi - 1];
          const obs = e.s + "_" + String(s.num[k]).padStart(4, "0") + "_" + s.sub[k];
          const w = waveAt(m.model.wave[det], px, py);
          out.push({ obs: obs, det: det, mjd: e.t0 + s.t[k], release: release, deep: !!((bits >> 14) & 1),
                     key: keyOf(release, e.s, ver, obs, det), px: px, py: py, lam: w[0], bw: w[1] });
        }
      }
      if (opts.onProgress) opts.onProgress(++done, hits.length);
    });
    out.sort((p, q) => p.mjd - q.mjd || p.det - q.det);
    return { frames: out, segments: hits.length, manifest: m };
  }

  /** Choose n frames spread evenly through a time-ordered list, each with stand-ins to try
      if it cannot be used. Bursts of consecutive exposures survive, as they do in the build. */
  function pick(frames, n) {
    n = Math.min(n, frames.length);
    const slots = [];
    for (let i = 0; i < n; i++) {
      const j = Math.round(i * (frames.length - 1) / Math.max(n - 1, 1));
      slots.push([j, j + 1, j - 1, j + 2].filter(k => k >= 0 && k < frames.length).map(k => frames[k]));
    }
    return slots;
  }

  const waves = new Map();

  /** The exact wavelength table for one detector of one release, read once from a real file. */
  function waveFor(release, det, key, signal) {
    const k = release + "/" + det;
    if (!waves.has(k)) waves.set(k, waveTable(key, signal).catch(e => { waves.delete(k); throw e; }));
    return waves.get(k);
  }

  /** Download a series of cutouts. `slots` comes from pick(); the result is in time order.
      opts: size (pixels), scale (degrees per pixel), ss, signal, onFrame(frame, count). */
  async function series(ra, dec, slots, opts) {
    const out = [], seen = new Set();
    await pool(slots, 6, async tries => {
      for (const c of tries) {
        if (opts.signal && opts.signal.aborted) return;
        if (seen.has(c.key)) continue;
        seen.add(c.key);
        try {
          const img = await openImage(c.key, opts.signal);
          const pl = plan(img.wcs, ra, dec, opts.size, opts.scale, opts.ss);
          if (!fits(img, pl)) continue;
          const cut = await cutout(img, ra, dec, opts.size, { plan: pl, signal: opts.signal });
          if (!cut || cut.finite < 0.9) continue;
          const w = waveAt(await waveFor(c.release, c.det, c.key, opts.signal), cut.tx, cut.ty);
          const f = { cand: c, img: img, data: cut.data, finite: cut.finite, lam: w[0], bw: w[1], x: cut.tx, y: cut.ty };
          out.push(f);
          if (opts.onFrame) opts.onFrame(f, out.length);
          return;
        } catch (e) {
          if (opts.signal && opts.signal.aborted) return;
          if (!e.notFound && typeof console !== "undefined") console.warn("skipped " + c.key + ": " + e.message);
        }
      }
    });
    return out.sort((p, q) => p.img.mjd - q.img.mjd || p.cand.det - q.cand.det);
  }

  root.SXLive = {
    S3: S3, PIXSCALE: PIXSCALE, stats: stats, index: index,
    range: range, tail: tail, list: list, parseHeader: parseHeader, makeWcs: makeWcs, frame: frame, unit: unit,
    openImage: openImage, plan: plan, fits: fits, cutout: cutout, waveTable: waveTable, waveAt: waveAt,
    openFlags: openFlags, flagRows: flagRows, flagCutout: flagCutout, unrice: unrice,
    weekVersions: weekVersions, keyOf: keyOf, openExposure: openExposure, releaseOf: releaseOf, weekOf: weekOf,
    manifest: manifest, search: search, pick: pick, series: series, locate: locate
  };
})(typeof window !== "undefined" ? window : globalThis);
