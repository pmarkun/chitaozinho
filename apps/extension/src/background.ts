import {
  DOMAINS,
  base64UrlEncode,
  bytesToHex,
  sha256Identifier,
  signCanonicalWithKey,
} from "@chitaozinho/protocol";

import {
  completeArtifact,
  createSession,
  declareArtifactUnavailable,
  finalizeSession,
  packageHashUrl,
  packageUrl,
  registerKey,
  sendEvent,
  uploadPart,
} from "./api";
import { advanceSession, nextEntry, signedEntry } from "./chain";
import {
  currentSession,
  deleteLocalSession,
  getSession,
  latestSession,
  savePart,
  saveReceipt,
  saveSession,
  sessionParts,
} from "./db";
import { incrementalSha256Identifier, totalByteLength } from "./hash";
import { decodeMessageBytes } from "./message-bytes";
import type { ExtensionMessage, PartRecord, SessionRecord } from "./types";

let operationQueue = Promise.resolve<unknown>(undefined);

chrome.runtime.onMessage.addListener(
  (
    message: ExtensionMessage,
    _sender,
    sendResponse: (value?: unknown) => void,
  ) => {
    if (message.type === "RECORDER_START" || message.type === "RECORDER_STOP") {
      return false;
    }
    if (message.type === "STOP_CAPTURE") {
      void stopRecorderAndFinalize()
        .then((result) => sendResponse({ ok: true, result }))
        .catch(async (error: unknown) => {
          await recordOperationError(error);
          sendResponse({ ok: false, error: String(error) });
        });
      return true;
    }
    operationQueue = operationQueue
      .then(() => handleMessage(message))
      .then((result) => sendResponse({ ok: true, result }))
      .catch(async (error: unknown) => {
        await recordOperationError(error);
        sendResponse({ ok: false, error: String(error) });
      });
    return true;
  },
);

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.url) {
    operationQueue = operationQueue.then(async () => {
      const session = await currentSession();
      if (session?.tabId === tabId && session.status === "recording") {
        await appendEvent(session, "navigation", { url: changeInfo.url });
      }
    });
  }
});

async function handleMessage(message: ExtensionMessage): Promise<unknown> {
  switch (message.type) {
    case "GET_STATE": {
      const latest = await latestSession();
      if (
        latest?.status === "recording" &&
        latest.recordingActive &&
        !(await chrome.offscreen.hasDocument())
      ) {
        latest.status = "interrupted";
        latest.error =
          "O contexto de gravação foi encerrado; retome a captura.";
        await saveSession(latest);
      }
      const { dismissedSessionId } =
        await chrome.storage.local.get("dismissedSessionId");
      return latest?.id === dismissedSessionId ? null : publicState(latest);
    }
    case "DISMISS_RESULT": {
      const latest = await latestSession();
      if (latest?.status === "complete") {
        await chrome.storage.local.set({ dismissedSessionId: latest.id });
      }
      return null;
    }
    case "DISCARD_FAILED_CAPTURE": {
      const latest = await currentSession();
      if (
        !latest ||
        !["error", "interrupted"].includes(latest.status) ||
        latest.captureFinished ||
        latest.recordingActive
      ) {
        throw new Error("capture cannot be discarded in its current state");
      }
      await deleteLocalSession(latest.id);
      await chrome.storage.local.set({ dismissedSessionId: latest.id });
      return null;
    }
    case "START_CAPTURE":
      if (!message.consent) throw new Error("consent is required");
      return publicState(await startCapture());
    case "RESUME_CAPTURE":
      return publicState(await resumeCapture());
    case "RECORDER_CHUNK":
      if (!message.sessionId || !message.bytesBase64)
        throw new Error("invalid recorder chunk");
      await persistAndUploadPart(
        message.sessionId,
        "recording",
        decodeMessageBytes(message.bytesBase64),
      );
      return undefined;
    case "ADD_MARKER": {
      const session = requireActive(await currentSession());
      await appendEvent(session, "marker", { note: message.note ?? "" });
      return publicState(await getSession(session.id));
    }
    case "ADD_SCREENSHOT": {
      const session = requireActive(await currentSession());
      await captureScreenshot(session, `screenshot-${session.nextSequence}`);
      return publicState(await getSession(session.id));
    }
    case "SCROLL": {
      const session = requireActive(await currentSession());
      await appendEvent(session, "scroll", message.eventData ?? {});
      return undefined;
    }
    default:
      return undefined;
  }
}

async function stopRecorderAndFinalize(): Promise<Record<
  string,
  unknown
> | null> {
  const session = requireActive(await currentSession());
  const recordingWasActive = session.recordingActive;
  if (recordingWasActive) {
    const stopped = await chrome.runtime.sendMessage({
      type: "RECORDER_STOP",
    } satisfies ExtensionMessage);
    if (!stopped?.ok) {
      throw new Error(String(stopped?.error ?? "recorder did not stop"));
    }
  }
  const finalization = operationQueue.then(async () => {
    const current = requireActive(await currentSession());
    current.recordingActive = false;
    await saveSession(current);
    return publicState(await stopCapture(recordingWasActive));
  });
  operationQueue = finalization.catch(() => undefined);
  return finalization;
}

async function recordOperationError(error: unknown): Promise<void> {
  const session = await currentSession();
  if (session && session.status !== "complete") {
    session.status = "error";
    session.error = String(error);
    await saveSession(session);
  }
}

async function startCapture(): Promise<SessionRecord> {
  if (await currentSession()) throw new Error("a capture is already active");
  await chrome.storage.local.remove("dismissedSessionId");
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab.id || tab.windowId === undefined)
    throw new Error("active tab is unavailable");
  const created = await createSession();
  const sessionId = String(created.session_id);
  const keyPair = (await crypto.subtle.generateKey("Ed25519", true, [
    "sign",
    "verify",
  ])) as CryptoKeyPair;
  const publicKey = new Uint8Array(
    await crypto.subtle.exportKey("raw", keyPair.publicKey),
  );
  const exportedPrivateKey = new Uint8Array(
    await crypto.subtle.exportKey("pkcs8", keyPair.privateKey),
  );
  const privateKey = await crypto.subtle.importKey(
    "pkcs8",
    exportedPrivateKey,
    "Ed25519",
    false,
    ["sign"],
  );
  exportedPrivateKey.fill(0);
  const keyId = `client-${crypto.randomUUID()}`;
  await registerKey(sessionId, keyId, publicKey);
  let session: SessionRecord = {
    id: sessionId,
    challenge: String(created.server_challenge),
    keyId,
    publicKey,
    privateKey,
    clockId: crypto.randomUUID(),
    clockStartedAt: Date.now(),
    nextSequence: Number(created.next_sequence ?? 0),
    previousEntryHash: null,
    tabId: tab.id,
    windowId: tab.windowId,
    startedAt: new Date().toISOString(),
    status: "starting",
    uploadedParts: 0,
    durationMs: 0,
    recordingActive: false,
    captureFinished: false,
    artifacts: [],
  };
  await saveSession(session);
  session = await appendEvent(session, "capture_started", {
    consent: true,
    url: tab.url ?? null,
    title: tab.title ?? null,
    software: __CHITAOZINHO_BUILD__,
  });
  await captureInitialArtifacts(session, tab);
  session = (await getSession(session.id)) ?? session;
  try {
    await ensureOffscreenDocument();
    const streamId = await chrome.tabCapture.getMediaStreamId({
      targetTabId: tab.id,
    });
    const started = await chrome.runtime.sendMessage({
      type: "RECORDER_START",
      streamId,
      sessionId,
    } satisfies ExtensionMessage);
    if (started?.error) throw new Error(String(started.error));
    session.recordingActive = true;
  } catch (error) {
    await declareUnavailable(
      session.id,
      "recording",
      "capture/recording.webm",
      "video/webm",
      "MediaRecorder",
      `tab recording unavailable: ${String(error)}`,
    );
    session = requireActive(await getSession(session.id));
    session.recordingActive = false;
  }
  session.status = "recording";
  await saveSession(session);
  await installScrollObserver(tab.id);
  return session;
}

async function resumeCapture(): Promise<SessionRecord> {
  let session = requireActive(await currentSession());
  if (session.status !== "interrupted" && session.status !== "error") {
    throw new Error("capture is not interrupted");
  }
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab.id || tab.windowId === undefined)
    throw new Error("active tab is unavailable");
  await retryPendingParts(session.id);
  session = requireActive(await getSession(session.id));
  session.clockId = crypto.randomUUID();
  session.clockStartedAt = Date.now();
  session.tabId = tab.id;
  session.windowId = tab.windowId;
  session.error = undefined;
  session = await appendEvent(session, "clock_restarted", {
    reason: "capture resumed after browser or extension interruption",
  });
  await ensureOffscreenDocument();
  const streamId = await chrome.tabCapture.getMediaStreamId({
    targetTabId: tab.id,
  });
  const started = await chrome.runtime.sendMessage({
    type: "RECORDER_START",
    streamId,
    sessionId: session.id,
  } satisfies ExtensionMessage);
  if (started?.error) throw new Error(String(started.error));
  session.recordingActive = true;
  session.status = "recording";
  await saveSession(session);
  await installScrollObserver(tab.id);
  return session;
}

async function captureInitialArtifacts(
  session: SessionRecord,
  tab: chrome.tabs.Tab,
) {
  await captureScreenshot(session, "screenshot-initial");
  let page:
    | {
        html: string;
        text: string;
        url: string;
        title: string;
        screen: { width: number; height: number };
        viewport: { width: number; height: number };
      }
    | undefined;
  try {
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: session.tabId },
      func: () => ({
        html: document.documentElement.outerHTML.slice(0, 4_000_000),
        text: document.body?.innerText.slice(0, 1_000_000) ?? "",
        url: location.href,
        title: document.title,
        screen: { width: window.screen.width, height: window.screen.height },
        viewport: { width: window.innerWidth, height: window.innerHeight },
      }),
    });
    page = result as typeof page;
    if (!page) throw new Error("page script returned no result");
    await uploadWholeArtifact(
      session.id,
      "dom",
      new TextEncoder().encode(page.html).buffer,
      "capture/dom.html",
      "text/html",
      "DOM serialization",
    );
  } catch (error) {
    await declareUnavailable(
      session.id,
      "dom",
      "capture/dom.html",
      "text/html",
      "DOM serialization",
      `DOM access unavailable: ${String(error)}`,
    );
  }
  await uploadWholeArtifact(
    session.id,
    "metadata",
    new TextEncoder().encode(
      JSON.stringify({
        url: page?.url ?? tab.url ?? null,
        title: page?.title ?? tab.title ?? null,
        visible_text: page?.text ?? null,
        user_agent: navigator.userAgent,
        screen: page?.screen ?? null,
        viewport: page?.viewport ?? {
          width: tab.width ?? null,
          height: tab.height ?? null,
        },
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        provenance: "client_reported",
      }),
    ).buffer,
    "capture/metadata.json",
    "application/json",
    "browser metadata",
  );
}

async function captureScreenshot(
  session: SessionRecord,
  artifactId: string,
): Promise<void> {
  try {
    const dataUrl = await chrome.tabs.captureVisibleTab(session.windowId, {
      format: "png",
    });
    const bytes = await (await fetch(dataUrl)).arrayBuffer();
    await uploadWholeArtifact(
      session.id,
      artifactId,
      bytes,
      `capture/${artifactId}.png`,
      "image/png",
      "captureVisibleTab",
    );
  } catch (error) {
    await declareUnavailable(
      session.id,
      artifactId,
      `capture/${artifactId}.png`,
      "image/png",
      "captureVisibleTab",
      `viewport screenshot unavailable: ${String(error)}`,
    );
  }
}

async function uploadWholeArtifact(
  sessionId: string,
  artifactId: string,
  bytes: ArrayBuffer,
  path: string,
  mediaType: string,
  method: string,
): Promise<void> {
  await persistAndUploadPart(sessionId, artifactId, bytes);
  await completeStoredArtifact(sessionId, artifactId, path, mediaType, method);
}

async function persistAndUploadPart(
  sessionId: string,
  artifactId: string,
  bytes: ArrayBuffer,
): Promise<void> {
  const session = requireActive(await getSession(sessionId));
  const parts = (await sessionParts(sessionId)).filter(
    (part) => part.artifactId === artifactId,
  );
  const partNumber = parts.length;
  const hash = sha256Identifier(new Uint8Array(bytes));
  const entry = nextEntry(session, "artifact_part", {
    artifact_id: artifactId,
    part_number: partNumber,
    part_hash: hash,
  });
  const signed = await signedEntry(session, entry);
  const part: PartRecord = {
    id: `${sessionId}:${artifactId}:${partNumber}`,
    sessionId,
    artifactId,
    partNumber,
    bytes,
    hash,
    entry,
    entryHash: signed.entry_hash,
    signatureHex: signed.signature_hex,
    state: "pending",
  };
  await savePart(part);
  await uploadPendingPart(session, part);
}

async function uploadPendingPart(
  session: SessionRecord,
  part: PartRecord,
): Promise<void> {
  const receipt = await uploadPart(
    session.id,
    part.artifactId,
    part.partNumber,
    part.bytes,
    {
      entry: part.entry,
      entry_hash: part.entryHash,
      signature_hex: part.signatureHex,
    },
  );
  part.state = "uploaded";
  await savePart(part);
  await saveReceipt({
    id: part.id,
    sessionId: session.id,
    artifactId: part.artifactId,
    partNumber: part.partNumber,
    receipt,
    receiptHash: String(receipt.receipt_hash),
    receiptSignatureHex: String(receipt.receipt_signature_hex),
  });
  session = advanceSession(session, part.entryHash);
  session.uploadedParts += 1;
  await saveSession(session);
}

async function retryPendingParts(sessionId: string): Promise<void> {
  const pending = (await sessionParts(sessionId))
    .filter((part) => part.state === "pending")
    .sort((left, right) => left.entry.sequence - right.entry.sequence);
  for (const part of pending) {
    const session = requireActive(await getSession(sessionId));
    if (part.entry.sequence !== session.nextSequence) {
      throw new Error("pending part is not the next chain entry");
    }
    await uploadPendingPart(session, part);
  }
}

async function completeStoredArtifact(
  sessionId: string,
  artifactId: string,
  path: string,
  mediaType: string,
  method: string,
): Promise<void> {
  let session = requireActive(await getSession(sessionId));
  const parts = (await sessionParts(sessionId))
    .filter((part) => part.artifactId === artifactId)
    .sort((left, right) => left.partNumber - right.partNumber);
  if (!parts.length || parts.some((part) => part.state !== "uploaded")) {
    throw new Error(`artifact ${artifactId} has pending parts`);
  }
  const partBytes = parts.map((part) => part.bytes);
  const artifactHash = incrementalSha256Identifier(partBytes);
  const artifactSize = totalByteLength(partBytes);
  const entry = nextEntry(session, "artifact_completed", {
    artifact_id: artifactId,
    artifact_hash: artifactHash,
  });
  const signed = await signedEntry(session, entry);
  await completeArtifact(sessionId, artifactId, {
    entry: signed,
    part_count: parts.length,
    size: artifactSize,
    artifact_hash: artifactHash,
    path,
    media_type: mediaType,
    method,
    provenance: "client_reported",
  });
  session = advanceSession(session, signed.entry_hash);
  session.artifacts.push({
    artifact_id: artifactId,
    path,
    size: artifactSize,
    status: "captured",
    artifact_hash: artifactHash,
  });
  await saveSession(session);
}

async function stopCapture(
  recordingWasActive: boolean,
): Promise<SessionRecord> {
  let session = requireActive(await currentSession());
  session.status = "finalizing";
  session.error = undefined;
  await saveSession(session);
  const hasRecordingResult = session.artifacts.some(
    (artifact) => artifact.artifact_id === "recording",
  );
  const recordingParts = (await sessionParts(session.id)).filter(
    (part) => part.artifactId === "recording",
  );
  if (
    !hasRecordingResult &&
    (recordingWasActive || recordingParts.length > 0)
  ) {
    session = requireActive(await getSession(session.id));
    if (recordingParts.length > 0) {
      await completeStoredArtifact(
        session.id,
        "recording",
        "capture/recording.webm",
        "video/webm",
        "MediaRecorder",
      );
    } else {
      await declareUnavailable(
        session.id,
        "recording",
        "capture/recording.webm",
        "video/webm",
        "MediaRecorder",
        "tab recording produced no data",
      );
    }
  }
  session = requireActive(await getSession(session.id));
  if (!session.captureFinished) {
    session = await appendEvent(session, "capture_finished", {
      duration_ms: Date.now() - new Date(session.startedAt).getTime(),
    });
    session.captureFinished = true;
    await saveSession(session);
  }
  const captureClose = {
    protocol_version: "0.1.0",
    session_id: session.id,
    session_root: session.previousEntryHash,
    last_entry_hash: session.previousEntryHash,
    entry_count: session.nextSequence,
    artifacts: [...session.artifacts].sort((left, right) =>
      left.artifact_id.localeCompare(right.artifact_id),
    ),
    known_gaps: session.artifacts
      .filter((artifact) => artifact.status !== "captured")
      .map(
        (artifact) =>
          `${artifact.artifact_id}: ${artifact.reason ?? artifact.status}`,
      ),
    client_key_id: session.keyId,
    client_public_key: base64UrlEncode(session.publicKey),
  };
  if (!session.privateKey)
    throw new Error("private key was lost before finalization");
  const signatureHex = bytesToHex(
    await signCanonicalWithKey(
      DOMAINS.captureClose,
      captureClose,
      session.privateKey,
    ),
  );
  const result = await finalizeSession(session.id, captureClose, signatureHex);
  session.status = "complete";
  session.privateKey = null;
  session.durationMs = Date.now() - new Date(session.startedAt).getTime();
  void result;
  await saveSession(session);
  await chrome.downloads.download({
    url: packageUrl(session.id),
    filename: `chitaozinho-${session.id}.zip`,
    saveAs: true,
  });
  await chrome.downloads.download({
    url: packageHashUrl(session.id),
    filename: `chitaozinho-${session.id}.zip.sha256`,
    saveAs: false,
  });
  return session;
}

async function declareUnavailable(
  sessionId: string,
  artifactId: string,
  path: string,
  mediaType: string,
  method: string,
  reason: string,
): Promise<void> {
  let session = requireActive(await getSession(sessionId));
  const normalizedReason = reason.slice(0, 2_000);
  const entry = nextEntry(session, "artifact_unavailable", {
    artifact_id: artifactId,
    event_data: { status: "unavailable", reason: normalizedReason },
  });
  const signed = await signedEntry(session, entry);
  await declareArtifactUnavailable(sessionId, artifactId, {
    entry: signed,
    path,
    media_type: mediaType,
    method,
    provenance: "client_reported",
    status: "unavailable",
    reason: normalizedReason,
  });
  session = advanceSession(session, signed.entry_hash);
  session.artifacts.push({
    artifact_id: artifactId,
    path,
    size: 0,
    status: "unavailable",
    reason: normalizedReason,
  });
  await saveSession(session);
}

async function appendEvent(
  session: SessionRecord,
  type: string,
  eventData: Record<string, unknown>,
): Promise<SessionRecord> {
  const entry = nextEntry(session, type, { event_data: eventData });
  const signed = await signedEntry(session, entry);
  await sendEvent(session.id, signed, `${type}-${entry.sequence}`);
  const advanced = advanceSession(session, signed.entry_hash);
  await saveSession(advanced);
  return advanced;
}

async function ensureOffscreenDocument(): Promise<void> {
  if (await chrome.offscreen.hasDocument()) return;
  await chrome.offscreen.createDocument({
    url: "offscreen.html",
    reasons: [chrome.offscreen.Reason.USER_MEDIA],
    justification: "Record the user-selected active tab with MediaRecorder.",
  });
}

async function installScrollObserver(tabId: number): Promise<void> {
  await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      let timer: number | undefined;
      addEventListener(
        "scroll",
        () => {
          clearTimeout(timer);
          timer = window.setTimeout(() => {
            void chrome.runtime.sendMessage({
              type: "SCROLL",
              eventData: { x: scrollX, y: scrollY },
            });
          }, 250);
        },
        { passive: true },
      );
    },
  });
}

function requireActive(session: SessionRecord | undefined): SessionRecord {
  if (!session || session.status === "complete")
    throw new Error("no active capture");
  return session;
}

function publicState(
  session: SessionRecord | undefined,
): Record<string, unknown> | null {
  if (!session) return null;
  return {
    id: session.id,
    status: session.status,
    startedAt: session.startedAt,
    uploadedParts: session.uploadedParts,
    durationMs:
      session.status === "recording"
        ? Date.now() - new Date(session.startedAt).getTime()
        : session.durationMs,
    packageHash: session.packageHash,
    error: session.error,
    captureFinished: session.captureFinished,
    unavailableArtifacts: session.artifacts.filter(
      (artifact) => artifact.status !== "captured",
    ).length,
  };
}
