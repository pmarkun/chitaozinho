import { uploadPart } from "./api";
import { acknowledgePart, getSession, sessionParts } from "./db";
import type { PartRecord, ReceiptRecord, SessionRecord } from "./types";

function requireSession(session: SessionRecord | undefined): SessionRecord {
  if (!session || session.status === "complete") {
    throw new Error("active capture not found");
  }
  return session;
}

export async function uploadPendingPart(part: PartRecord): Promise<void> {
  const receipt = await uploadPart(
    part.sessionId,
    part.artifactId,
    part.partNumber,
    part.bytes,
    {
      entry: part.entry,
      entry_hash: part.entryHash,
      signature_hex: part.signatureHex,
    },
  );
  const session = requireSession(await getSession(part.sessionId));
  part.state = "uploaded";
  session.uploadedParts += 1;
  const receiptRecord: ReceiptRecord = {
    id: part.id,
    sessionId: part.sessionId,
    artifactId: part.artifactId,
    partNumber: part.partNumber,
    receipt,
    receiptHash: String(receipt.receipt_hash),
    receiptSignatureHex: String(receipt.receipt_signature_hex),
  };
  await acknowledgePart(session, part, receiptRecord);
}

export async function retryPendingParts(sessionId: string): Promise<void> {
  const pending = (await sessionParts(sessionId))
    .filter((part) => part.state === "pending")
    .sort((left, right) => left.entry.sequence - right.entry.sequence);
  for (const part of pending) {
    await uploadPendingPart(part);
  }
}
