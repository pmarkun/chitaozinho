import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, test } from "vitest";

import {
  DOMAINS,
  base64UrlDecode,
  base64UrlEncode,
  bytesToHex,
  canonicalBytes,
  hexToBytes,
  sha256Identifier,
  signCanonical,
  verifyCanonical,
} from "../src/index.js";

interface Vector {
  entry: Record<string, unknown>;
  canonical_json: string;
  sha256: string;
  private_seed_hex: string;
  public_key_hex: string;
  signature_hex: string;
  base64url: {
    bytes_hex: string;
    encoded: string;
  };
}

const vector = JSON.parse(
  readFileSync(
    resolve(process.cwd(), "../../test-vectors/protocol-v0.1.json"),
    "utf8",
  ),
) as Vector;

describe("protocol vector", () => {
  test("canonicalizes and hashes identically", () => {
    expect(new TextDecoder().decode(canonicalBytes(vector.entry))).toBe(
      vector.canonical_json,
    );
    expect(sha256Identifier(canonicalBytes(vector.entry))).toBe(vector.sha256);
  });

  test("signs and verifies with Ed25519 Web Crypto", async () => {
    const signature = await signCanonical(
      DOMAINS.entry,
      vector.entry,
      hexToBytes(vector.private_seed_hex),
    );
    expect(bytesToHex(signature)).toBe(vector.signature_hex);
    await expect(
      verifyCanonical(
        DOMAINS.entry,
        vector.entry,
        signature,
        hexToBytes(vector.public_key_hex),
      ),
    ).resolves.toBe(true);
  });

  test("rejects altered content, domain and signature", async () => {
    const signature = hexToBytes(vector.signature_hex);
    const publicKey = hexToBytes(vector.public_key_hex);
    await expect(
      verifyCanonical(
        DOMAINS.entry,
        { ...vector.entry, sequence: 2 },
        signature,
        publicKey,
      ),
    ).resolves.toBe(false);
    await expect(
      verifyCanonical(DOMAINS.receipt, vector.entry, signature, publicKey),
    ).resolves.toBe(false);
    const alteredSignature = Uint8Array.from(signature);
    alteredSignature[0] = (alteredSignature[0] ?? 0) ^ 1;
    await expect(
      verifyCanonical(DOMAINS.entry, vector.entry, alteredSignature, publicKey),
    ).resolves.toBe(false);
  });

  test("uses Base64URL without padding", () => {
    const value = hexToBytes(vector.base64url.bytes_hex);
    expect(base64UrlEncode(value)).toBe(vector.base64url.encoded);
    expect(bytesToHex(base64UrlDecode(vector.base64url.encoded))).toBe(
      vector.base64url.bytes_hex,
    );
    expect(() => base64UrlDecode("AAEC-_8=")).toThrow();
  });
});
