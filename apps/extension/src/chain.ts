import {
  DOMAINS,
  bytesToHex,
  canonicalBytes,
  sha256Identifier,
  signCanonicalWithKey,
} from "@chitaozinho/protocol";

import type { ChainEntry, SessionRecord } from "./types";

export function nextEntry(
  session: SessionRecord,
  entryType: string,
  fields: Partial<ChainEntry> = {},
): ChainEntry {
  return {
    protocol_version: "0.1.0",
    entry_type: entryType,
    session_id: session.id,
    sequence: session.nextSequence,
    previous_entry_hash: session.previousEntryHash,
    client_clock_id: session.clockId,
    client_monotonic_time: Math.max(
      0,
      Math.round(
        (performance.timeOrigin + performance.now() - session.clockStartedAt) *
          1000,
      ),
    ),
    client_wall_time: new Date().toISOString(),
    server_challenge: session.challenge,
    ...fields,
  };
}

export async function signedEntry(
  session: SessionRecord,
  entry: ChainEntry,
): Promise<{ entry: ChainEntry; entry_hash: string; signature_hex: string }> {
  if (!session.privateKey) {
    throw new Error("session private key is unavailable");
  }
  return {
    entry,
    entry_hash: sha256Identifier(canonicalBytes(entry)),
    signature_hex: bytesToHex(
      await signCanonicalWithKey(DOMAINS.entry, entry, session.privateKey),
    ),
  };
}

export function advanceSession(
  session: SessionRecord,
  entryHash: string,
): SessionRecord {
  return {
    ...session,
    nextSequence: session.nextSequence + 1,
    previousEntryHash: entryHash,
  };
}
