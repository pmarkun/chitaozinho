import "fake-indexeddb/auto";

import { afterEach, expect, it, vi } from "vitest";

vi.mock("./api", () => ({
  uploadPart: vi.fn(),
}));

import { uploadPart } from "./api";
import {
  closeDatabase,
  getSession,
  saveQueuedPart,
  sessionParts,
  sessionReceipts,
} from "./db";
import { retryPendingParts } from "./part-upload";
import type { ChainEntry, PartRecord, SessionRecord } from "./types";

afterEach(async () => {
  await closeDatabase();
  await new Promise<void>((resolve, reject) => {
    const request = indexedDB.deleteDatabase("chitaozinho");
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
    request.onblocked = () => reject(new Error("database deletion blocked"));
  });
});

it("resumes an interrupted recording without duplicating parts or receipts", async () => {
  const entry: ChainEntry = {
    protocol_version: "0.1.0",
    entry_type: "artifact_part",
    session_id: "network-recovery",
    sequence: 4,
    previous_entry_hash: "sha256:previous",
    client_clock_id: "clock-1",
    client_monotonic_time: 4_000,
    client_wall_time: "2026-07-30T12:00:04.000Z",
    server_challenge: "challenge",
    artifact_id: "recording",
    part_number: 2,
    part_hash: "sha256:part",
  };
  const session: SessionRecord = {
    id: entry.session_id,
    challenge: entry.server_challenge,
    keyId: "client-key",
    publicKey: new Uint8Array([1]),
    privateKey: null,
    clockId: entry.client_clock_id,
    clockStartedAt: 1,
    nextSequence: 5,
    previousEntryHash: "sha256:queued-entry",
    tabId: 1,
    windowId: 1,
    startedAt: "2026-07-30T12:00:00.000Z",
    status: "error",
    uploadedParts: 2,
    durationMs: 4_000,
    recordingActive: true,
    captureFinished: false,
    artifacts: [],
    error: "TypeError: Failed to fetch",
  };
  const part: PartRecord = {
    id: `${session.id}:recording:2`,
    sessionId: session.id,
    artifactId: "recording",
    partNumber: 2,
    bytes: new Uint8Array([7, 8, 9]).buffer,
    hash: entry.part_hash!,
    entry,
    entryHash: session.previousEntryHash!,
    signatureHex: "abcd",
    state: "pending",
  };
  await saveQueuedPart(session, part);

  const mockedUpload = vi.mocked(uploadPart);
  mockedUpload.mockRejectedValueOnce(new TypeError("Failed to fetch"));
  await expect(retryPendingParts(session.id)).rejects.toThrow(
    "Failed to fetch",
  );

  expect(await sessionParts(session.id)).toEqual([part]);
  expect(await sessionReceipts(session.id)).toEqual([]);
  expect(await getSession(session.id)).toMatchObject({
    nextSequence: 5,
    uploadedParts: 2,
    status: "error",
  });

  mockedUpload.mockResolvedValueOnce({
    receipt_hash: "sha256:receipt",
    receipt_signature_hex: "ef01",
  });
  await retryPendingParts(session.id);
  await retryPendingParts(session.id);

  expect(mockedUpload).toHaveBeenCalledTimes(2);
  expect(mockedUpload.mock.calls[0]).toEqual(mockedUpload.mock.calls[1]);
  expect((await sessionParts(session.id))[0]).toMatchObject({
    id: part.id,
    state: "uploaded",
  });
  expect(await sessionReceipts(session.id)).toHaveLength(1);
  expect(await getSession(session.id)).toMatchObject({
    nextSequence: 5,
    uploadedParts: 3,
    status: "error",
  });
});
