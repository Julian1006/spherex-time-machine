/* Cache-first for everything this app owns, so it keeps working with no network.
   Frame data is cached the first time a target is opened rather than all at once: the
   full set is 16 MB and most people look at two or three. The one exception is the list of
   pointings behind the coordinate search, which is always asked of the network first. */
const VERSION = "sx-a0aaa113e3";
const SHELL = ["./", "./index.html", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png", "./cover.png"];
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
  if (!mine) return;                       // images from NASA's bucket go straight to the network
  const keep = res => {
    if (res && (res.ok || res.type === "opaque")) {
      const copy = res.clone();
      caches.open(VERSION).then(c => c.put(req, copy));
    }
    return res;
  };
  // The list of SPHEREx pointings is rebuilt every day: ask the network first, and fall back
  // to the last copy only when there is no network.
  if (url.origin === location.origin && /\/idx\/manifest\.json$/.test(url.pathname)) {
    e.respondWith(fetch(req).then(keep).catch(() => caches.match(req)));
    return;
  }
  // A link that carries coordinates (?ra=..&dec=..) is still this page.
  const page = req.mode === "navigate";
  e.respondWith(
    caches.match(req, {ignoreSearch: page}).then(hit => hit || fetch(req).then(res => page && url.search ? res : keep(res))
      .catch(() => caches.match("./index.html")))
  );
});
