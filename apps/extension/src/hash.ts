import { sha256 } from "@noble/hashes/sha2.js";

import { bytesToHex } from "@chitaozinho/protocol";

export function incrementalSha256Identifier(
  parts: readonly ArrayBuffer[],
): string {
  const digest = sha256.create();
  for (const part of parts) {
    digest.update(new Uint8Array(part));
  }
  return `sha256:${bytesToHex(digest.digest())}`;
}

export function totalByteLength(parts: readonly ArrayBuffer[]): number {
  return parts.reduce((total, part) => total + part.byteLength, 0);
}
