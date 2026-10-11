import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { describe, expect, it, vi } from "vitest";

const source = readFileSync(
  new URL("../public/sw.js", import.meta.url),
  "utf8",
);

function worker(hostname: string) {
  const listeners: Record<string, (event: unknown) => void> = {};
  const navigate = vi.fn().mockResolvedValue(undefined);
  const cache = { addAll: vi.fn().mockResolvedValue(undefined) };
  const caches = {
    keys: vi
      .fn()
      .mockResolvedValue(["chitaozinho-verifier-v0.3.2", "other-app"]),
    delete: vi.fn().mockResolvedValue(true),
    open: vi.fn().mockResolvedValue(cache),
  };
  const self = {
    location: { hostname, origin: `https://${hostname}` },
    addEventListener: (name: string, callback: (event: unknown) => void) => {
      listeners[name] = callback;
    },
    skipWaiting: vi.fn(),
    registration: { unregister: vi.fn().mockResolvedValue(true) },
    clients: {
      claim: vi.fn(),
      matchAll: vi
        .fn()
        .mockResolvedValue([
          { url: `https://${hostname}/validar?proof=1#resultado`, navigate },
        ]),
    },
  };
  runInNewContext(source, { self, caches, URL });
  return { listeners, self, caches, navigate, cache };
}

describe("production domain service worker migration", () => {
  it.each(["beta.evidencias.org.br", "www.evidencias.org.br"])(
    "retires the offline worker on %s without caching redirects",
    async (hostname) => {
      const state = worker(hostname);
      const waitUntil = vi.fn();
      state.listeners.install!({ waitUntil });
      expect(state.self.skipWaiting).toHaveBeenCalled();
      expect(state.caches.open).not.toHaveBeenCalled();
      state.listeners.activate!({ waitUntil });
      await waitUntil.mock.calls[0]![0];
      expect(state.caches.delete).toHaveBeenCalledExactlyOnceWith(
        "chitaozinho-verifier-v0.3.2",
      );
      expect(state.self.registration.unregister).toHaveBeenCalled();
      expect(state.navigate).toHaveBeenCalledExactlyOnceWith(
        "https://evidencias.org.br/validar?proof=1#resultado",
      );
      const respondWith = vi.fn();
      state.listeners.fetch!({ respondWith });
      expect(respondWith).not.toHaveBeenCalled();
    },
  );

  it("keeps offline verification on the canonical domain", async () => {
    const state = worker("evidencias.org.br");
    const waitUntil = vi.fn();
    state.listeners.install!({ waitUntil });
    await waitUntil.mock.calls[0]![0];
    expect(state.cache.addAll).toHaveBeenCalled();
    state.listeners.activate!({ waitUntil });
    await waitUntil.mock.calls[1]![0];
    expect(state.self.registration.unregister).not.toHaveBeenCalled();
    expect(state.navigate).not.toHaveBeenCalled();
  });
});
