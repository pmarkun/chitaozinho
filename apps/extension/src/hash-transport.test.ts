import { expect, test, vi } from "vitest";
import { uploadPart } from "./api";
import { getSession } from "./db";
import type { ChainEntry, SessionRecord } from "./types";

vi.mock("./db", () => ({ getSession: vi.fn() }));

test("hash-only transport never serializes the captured bytes", async () => {
  vi.mocked(getSession).mockResolvedValue({
    evidenceMode: "hash_only",
  } as SessionRecord);
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(new Response("{}"));
  const raw = new TextEncoder().encode("SENSITIVE_EVIDENCE_SENTINEL");
  try {
    await uploadPart("session", "metadata", 0, raw.buffer, {
      entry: { part_hash: `sha256:${"a".repeat(64)}` } as ChainEntry,
      entry_hash: "hash",
      signature_hex: "signature",
    });
    const [url, options] = fetch.mock.calls[0];
    expect(String(url)).toMatch(/\/parts\/0\/hash$/);
    expect(JSON.parse(options!.body as string)).toEqual({
      size: raw.byteLength,
      part_hash: `sha256:${"a".repeat(64)}`,
    });
    expect(JSON.stringify(fetch.mock.calls)).not.toContain(
      "SENSITIVE_EVIDENCE_SENTINEL",
    );
  } finally {
    fetch.mockRestore();
  }
});
