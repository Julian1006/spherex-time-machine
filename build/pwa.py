"""Make the web build installable as an app, and keep working once it is.

Only the site build gets this. An installable app needs a real origin - https, or localhost -
so it is deliberately absent from the offline bundle, which runs from file:// where a service
worker cannot register at all.
"""
import io, os, json, hashlib

MANIFEST = {
    "name": "SPHEREx Time Machine",
    "short_name": "SPHEREx",
    "description": "Watch a patch of sky change across fifteen months of real NASA SPHEREx images.",
    "start_url": "./",
    "scope": "./",
    "display": "standalone",
    "background_color": "#0E0D0C",
    "theme_color": "#0E0D0C",
    "categories": ["education", "science"],
    "icons": [
        {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
    ],
}

SW = """/* Cache-first for everything this app owns, so it keeps working with no network.
   Frame data is cached the first time a target is opened rather than all at once: the
   full set is 16 MB and most people look at two or three. */
const VERSION = "%s";
const SHELL = ["./", "./index.html", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png"];
const FONT_HOSTS = ["fonts.googleapis.com", "fonts.gstatic.com"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys()
    .then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const mine = url.origin === location.origin || FONT_HOSTS.indexOf(url.hostname) >= 0;
  if (!mine) return;
  e.respondWith(
    caches.match(req).then(hit => hit || fetch(req).then(res => {
      if (res && (res.ok || res.type === "opaque")) {
        const copy = res.clone();
        caches.open(VERSION).then(c => c.put(req, copy));
      }
      return res;
    }).catch(() => caches.match("./index.html")))
  );
});
"""

HEAD = """<link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#0E0D0C">
<link rel="apple-touch-icon" href="icon-192.png">
<link rel="icon" type="image/png" href="icon-192.png">
"""

REGISTER = """
<script>
/* A service worker only registers on a secure origin, so this quietly does nothing when the
   page is opened from a file. */
if ("serviceWorker" in navigator &&
    (location.protocol === "https:" || location.hostname === "localhost")) {
  addEventListener("load", function () {
    navigator.serviceWorker.register("sw.js").catch(function () {});
  });
}
</script>
"""


def install(site_dir, page_html):
    """Write the manifest and worker, and return the page with both wired in."""
    io.open(os.path.join(site_dir, 'manifest.webmanifest'), 'w', encoding='utf-8').write(
        json.dumps(MANIFEST, indent=2))
    version = "sx-" + hashlib.sha1(page_html.encode('utf-8')).hexdigest()[:10]
    io.open(os.path.join(site_dir, 'sw.js'), 'w', encoding='utf-8').write(SW % version)
    return HEAD + page_html + REGISTER, version
