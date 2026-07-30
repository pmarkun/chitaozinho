import { expect, test, vi } from "vitest";

import { nextEntry } from "./chain";
import type { SessionRecord } from "./types";

vi.stubGlobal("performance", {
  timeOrigin: 1_000,
  now: () => 250,
});

const session: SessionRecord = {
  id: "session",
  challenge: "challenge",
  keyId: "key",
  publicKey: new Uint8Array(32),
  privateKey: null,
  clockId: "clock",
  clockStartedAt: 1_000,
  nextSequence: 0,
  previousEntryHash: null,
  tabId: 1,
  windowId: 1,
  startedAt: "2026-07-30T00:00:00Z",
  status: "recording",
  uploadedParts: 0,
  durationMs: 0,
  recordingActive: false,
  captureFinished: false,
  artifacts: [],
};

test("creates the genesis entry with normalized sequence and monotonic time", () => {
  const entry = nextEntry(session, "capture_started");
  expect(entry.sequence).toBe(0);
  expect(entry.previous_entry_hash).toBeNull();
  expect(entry.client_clock_id).toBe("clock");
  expect(entry.client_monotonic_time).toBe(250_000);
});
