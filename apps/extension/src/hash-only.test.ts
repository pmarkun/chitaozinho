import "fake-indexeddb/auto";
import { readFileSync, writeFileSync } from "node:fs";
import { describe, expect, test, vi } from "vitest";
import {
  base64UrlEncode,
  bytesToHex,
  canonicalBytes,
  DOMAINS,
  sha256Identifier,
  signCanonicalWithKey,
} from "@chitaozinho/protocol";
import { assembleLocalPackage, hashBlob } from "./local-package";
import { nextEntry } from "./chain";
import type { LocalPackageTemplate, PartRecord, SessionRecord } from "./types";

const bytes = new TextEncoder().encode(
  "private evidence https://private.invalid",
);
const digest = sha256Identifier(bytes);
const part = {
  sessionId: "test",
  artifactId: "metadata",
  partNumber: 0,
  bytes: bytes.buffer,
  hash: digest,
} as PartRecord;

async function fixture(): Promise<LocalPackageTemplate> {
  const pair = (await crypto.subtle.generateKey("Ed25519", true, [
    "sign",
    "verify",
  ])) as CryptoKeyPair;
  const keys = canonicalBytes({
    server: {
      public_key_hex: bytesToHex(
        new Uint8Array(await crypto.subtle.exportKey("raw", pair.publicKey)),
      ),
    },
  });
  const index = {
    schema_version: "0.1.0",
    session_id: "test",
    members: [
      { path: "capture/metadata.json", size: bytes.length, sha256: digest },
      {
        path: "signatures/public-keys.json",
        size: keys.length,
        sha256: sha256Identifier(keys),
      },
    ],
  };
  return {
    evidence_mode: "hash_only",
    session_id: "test",
    artifacts: [
      {
        artifact_id: "metadata",
        path: "capture/metadata.json",
        size: bytes.length,
        sha256: digest,
      },
    ],
    members: {
      "package-index.json": base64UrlEncode(canonicalBytes(index)),
      "signatures/public-keys.json": base64UrlEncode(keys),
      "signatures/package-index.server.sig": base64UrlEncode(
        new TextEncoder().encode(
          bytesToHex(
            await signCanonicalWithKey(
              DOMAINS.packageIndex,
              index,
              pair.privateKey,
            ),
          ),
        ),
      ),
    },
  };
}

describe("hash-only local packaging", () => {
  test("creates a ZIP locally without any fetch", async () => {
    const fetch = vi.spyOn(globalThis, "fetch");
    try {
      const blob = await assembleLocalPackage(await fixture(), [part]);
      expect(blob.size).toBeGreaterThan(bytes.length);
      expect(await hashBlob(blob)).toMatch(/^sha256:[0-9a-f]{64}$/);
      expect(fetch).not.toHaveBeenCalled();
    } finally {
      fetch.mockRestore();
    }
  });
  test("rejects absent, changed, and duplicated local parts", async () => {
    const template = await fixture();
    for (const parts of [
      [],
      [{ ...part, bytes: new Uint8Array([0]).buffer }],
      [part, part],
    ]) {
      await expect(assembleLocalPackage(template, parts)).rejects.toThrow();
    }
  });
  test("rejects modified signed metadata", async () => {
    const template = await fixture();
    template.members["package-index.json"] = base64UrlEncode(
      canonicalBytes({ session_id: "other", members: [] }),
    );
    await expect(assembleLocalPackage(template, [part])).rejects.toThrow(
      "signature",
    );
  });
  test("commits event context without transmitting URL or title", () => {
    const session = {
      evidenceMode: "hash_only",
      id: "test",
      clockStartedAt: Date.now(),
      nextSequence: 0,
      previousEntryHash: null,
      clockId: "clock",
      challenge: "challenge",
    } as SessionRecord;
    const entry = nextEntry(session, "capture_started", {
      event_data: { url: "https://private.invalid", title: "PRIVATE_TITLE" },
    });
    expect(entry.event_data).toEqual({
      commitment: expect.stringMatching(/^sha256:/),
    });
    expect(JSON.stringify(entry)).not.toContain("private.invalid");
    expect(JSON.stringify(entry)).not.toContain("PRIVATE_TITLE");
    expect(
      nextEntry({ ...session, evidenceMode: "remote" }, "capture_started", {
        event_data: { url: "legacy" },
      }).event_data,
    ).toEqual({ url: "legacy" });
  });
  test.skipIf(!process.env.HASH_ONLY_TEST_OUTPUT)(
    "assembles the real Python API template for cross-runtime verification",
    async () => {
      const root = process.env.HASH_ONLY_TEST_OUTPUT!;
      const fixture = JSON.parse(readFileSync(`${root}/template.json`, "utf8"));
      const raw = new Uint8Array(Buffer.from(fixture.content, "base64"));
      const blob = await assembleLocalPackage(fixture.template, [
        {
          ...part,
          sessionId: fixture.template.session_id,
          bytes: raw.buffer,
          hash: sha256Identifier(raw),
        },
      ]);
      writeFileSync(
        `${root}/client-evidence.zip`,
        new Uint8Array(await blob.arrayBuffer()),
      );
      writeFileSync(
        `${root}/client-evidence.zip.sha256`,
        (await hashBlob(blob)).slice(7),
      );
    },
  );
});
