import "fake-indexeddb/auto";

import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  ChainEntry,
  PartRecord,
  ReceiptRecord,
  SessionRecord,
} from "./types";

describe("capture database", () => {
  afterEach(async () => {
    const { closeDatabase } = await import("./db");
    await closeDatabase();
    await new Promise<void>((resolve, reject) => {
      const request = indexedDB.deleteDatabase("chitaozinho");
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
      request.onblocked = () => reject(new Error("database deletion blocked"));
    });
    vi.resetModules();
  });

  it("recovers sessions, pending bytes and receipts after reopening", async () => {
    const first = await import("./db");
    const entry: ChainEntry = {
      protocol_version: "0.1.0",
      entry_type: "artifact_part",
      session_id: "session-1",
      sequence: 1,
      previous_entry_hash: null,
      client_clock_id: "clock-1",
      client_monotonic_time: 123,
      client_wall_time: "2026-07-30T12:00:00.000Z",
      server_challenge: "challenge",
      artifact_id: "video",
      part_number: 0,
      part_hash: "sha256:part",
    };
    const session: SessionRecord = {
      id: "session-1",
      challenge: "challenge",
      keyId: "key-1",
      publicKey: new Uint8Array([1, 2, 3]),
      privateKey: null,
      clockId: "clock-1",
      clockStartedAt: 123,
      nextSequence: 2,
      previousEntryHash: "sha256:entry",
      tabId: 10,
      windowId: 20,
      startedAt: "2026-07-30T12:00:00.000Z",
      status: "interrupted",
      uploadedParts: 0,
      durationMs: 60_000,
      recordingActive: false,
      captureFinished: false,
      artifacts: [],
      error: "network unavailable",
    };
    const part: PartRecord = {
      id: "session-1:video:0",
      sessionId: "session-1",
      artifactId: "video",
      partNumber: 0,
      bytes: new Uint8Array([4, 5, 6]).buffer,
      hash: "sha256:part",
      entry,
      entryHash: "sha256:entry",
      signatureHex: "abcd",
      state: "pending",
    };
    const receipt: ReceiptRecord = {
      id: "session-1:metadata:0",
      sessionId: "session-1",
      artifactId: "metadata",
      partNumber: 0,
      receipt: { receipt_id: "receipt-1" },
      receiptHash: "sha256:receipt",
      receiptSignatureHex: "ef01",
    };

    await first.saveSession(session);
    await first.savePart(part);
    await first.saveReceipt(receipt);
    await first.closeDatabase();
    vi.resetModules();

    const reopened = await import("./db");
    expect(await reopened.currentSession()).toMatchObject({
      id: "session-1",
      status: "interrupted",
      error: "network unavailable",
    });
    const [recoveredPart] = await reopened.sessionParts("session-1");
    expect(recoveredPart.state).toBe("pending");
    expect(new Uint8Array(recoveredPart.bytes)).toEqual(
      new Uint8Array([4, 5, 6]),
    );
    expect(await reopened.sessionReceipts("session-1")).toEqual([receipt]);
  });

  it("deletes a failed session only after an explicit local discard", async () => {
    const database = await import("./db");
    const session: SessionRecord = {
      id: "failed-session",
      challenge: "challenge",
      keyId: "key",
      publicKey: new Uint8Array([1]),
      privateKey: null,
      clockId: "clock",
      clockStartedAt: 1,
      nextSequence: 0,
      previousEntryHash: null,
      tabId: 1,
      windowId: 1,
      startedAt: "2026-07-30T12:00:00.000Z",
      status: "error",
      uploadedParts: 0,
      durationMs: 0,
      recordingActive: false,
      captureFinished: false,
      artifacts: [],
    };
    await database.saveSession(session);

    expect(await database.getSession(session.id)).toBeDefined();
    await database.deleteLocalSession(session.id);
    expect(await database.getSession(session.id)).toBeUndefined();
  });
});
