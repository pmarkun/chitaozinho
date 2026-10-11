const CACHE_NAME = "evidencias-verifier-v0.1.9";
const APP_SHELL = ["/", "/index.html", "/manifest.webmanifest"];
const LEGACY_HOST = [
  "beta.evidencias.org.br",
  "www.evidencias.org.br",
].includes(self.location.hostname);

self.addEventListener("install", (event) => {
  if (LEGACY_HOST) {
    self.skipWaiting();
    return;
  }
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  if (LEGACY_HOST) {
    event.waitUntil(
      (async () => {
        const names = await caches.keys();
        await Promise.all(
          names
            .filter(
              (name) =>
                name.startsWith("evidencias-verifier-") ||
                name.startsWith("chitaozinho-verifier-"),
            )
            .map((name) => caches.delete(name)),
        );
        await self.registration.unregister();
        const clients = await self.clients.matchAll({ type: "window" });
        await Promise.all(
          clients.map((client) => {
            const url = new URL(client.url);
            if (url.origin !== self.location.origin) return;
            return client.navigate(
              `https://evidencias.org.br${url.pathname}${url.search}${url.hash}`,
            );
          }),
        );
      })(),
    );
    return;
  }
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names
            .filter((name) => name !== CACHE_NAME)
            .map((name) => caches.delete(name)),
        ),
      ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (LEGACY_HOST) return;
  if (event.request.method !== "GET") return;
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request).catch(() => caches.match("/index.html")),
    );
    return;
  }
  event.respondWith(
    caches.match(event.request).then(
      (cached) =>
        cached ??
        fetch(event.request).then((response) => {
          if (
            !response.ok ||
            new URL(event.request.url).origin !== self.location.origin
          ) {
            return response;
          }
          const copy = response.clone();
          caches
            .open(CACHE_NAME)
            .then((cache) => cache.put(event.request, copy));
          return response;
        }),
    ),
  );
});
