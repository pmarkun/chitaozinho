import { openDB, type DBSchema } from "idb";

import type { PartRecord, ReceiptRecord, SessionRecord } from "./types";

interface ChitaozinhoDatabase extends DBSchema {
  sessions: {
    key: string;
    value: SessionRecord;
  };
  parts: {
    key: string;
    value: PartRecord;
    indexes: { "by-session": string };
  };
  receipts: {
    key: string;
    value: ReceiptRecord;
    indexes: { "by-session": string };
  };
}

const database = openDB<ChitaozinhoDatabase>("chitaozinho", 1, {
  upgrade(store) {
    store.createObjectStore("sessions", { keyPath: "id" });
    const parts = store.createObjectStore("parts", { keyPath: "id" });
    parts.createIndex("by-session", "sessionId");
    const receipts = store.createObjectStore("receipts", { keyPath: "id" });
    receipts.createIndex("by-session", "sessionId");
  },
});

export async function saveSession(session: SessionRecord): Promise<void> {
  await (await database).put("sessions", session);
}

export async function getSession(
  id: string,
): Promise<SessionRecord | undefined> {
  return (await database).get("sessions", id);
}

export async function currentSession(): Promise<SessionRecord | undefined> {
  return (await allSessions()).find((session) => session.status !== "complete");
}

export async function latestSession(): Promise<SessionRecord | undefined> {
  return (await allSessions())[0];
}

async function allSessions(): Promise<SessionRecord[]> {
  const sessions = await (await database).getAll("sessions");
  return sessions.sort((left, right) =>
    right.startedAt.localeCompare(left.startedAt),
  );
}

export async function savePart(part: PartRecord): Promise<void> {
  await (await database).put("parts", part);
}

export async function sessionParts(sessionId: string): Promise<PartRecord[]> {
  return (await database).getAllFromIndex("parts", "by-session", sessionId);
}

export async function saveReceipt(receipt: ReceiptRecord): Promise<void> {
  await (await database).put("receipts", receipt);
}

export async function sessionReceipts(
  sessionId: string,
): Promise<ReceiptRecord[]> {
  return (await database).getAllFromIndex("receipts", "by-session", sessionId);
}
