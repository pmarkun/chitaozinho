import type { ExtensionMessage } from "./types";
import { encodeMessageBytes } from "./message-bytes";
import { localPackageUrls } from "./local-package";
import { preserveTabAudio } from "./audio";
import { captureConstraints } from "./capture-source";

let recorder: MediaRecorder | undefined;
let stream: MediaStream | undefined;
let sessionId: string | undefined;
const pendingChunks = new Set<Promise<void>>();
let chunkError: unknown;
let closeAudio: (() => Promise<void>) | undefined;
let mediaRelease = Promise.resolve();

chrome.runtime.onMessage.addListener(
  (
    message: ExtensionMessage,
    _sender,
    sendResponse: (value?: unknown) => void,
  ) => {
    if (message.type === "BUILD_LOCAL_PACKAGE" && message.sessionId) {
      void localPackageUrls(message.sessionId, message.template).then(
        (result) => sendResponse({ ok: true, result }),
        (error: unknown) => sendResponse({ ok: false, error: String(error) }),
      );
      return true;
    }
    if (
      message.type === "RECORDER_START" &&
      message.streamId &&
      message.sessionId
    ) {
      void startRecording(
        message.streamId,
        message.sessionId,
        message.captureSource ?? "tab",
        message.audio ?? true,
      )
        .then((result) => sendResponse({ ok: true, result }))
        .catch((error: unknown) => sendResponse({ error: String(error) }));
      return true;
    }
    if (message.type === "RECORDER_STOP") {
      void stopRecording()
        .then(() => sendResponse({ ok: true }))
        .catch((error: unknown) => sendResponse({ error: String(error) }));
      return true;
    }
    return false;
  },
);

async function startRecording(
  streamId: string,
  captureSessionId: string,
  source: "tab" | "desktop",
  audio: boolean,
): Promise<{ audio: boolean }> {
  if (recorder?.state === "recording") {
    throw new Error("recorder is already active");
  }
  chunkError = undefined;
  sessionId = captureSessionId;
  stream = await navigator.mediaDevices.getUserMedia(
    captureConstraints(source, streamId, audio),
  );
  try {
    if (source === "tab") closeAudio = await preserveTabAudio(stream);
    recorder = new MediaRecorder(stream, {
      mimeType: preferredMimeType(),
      videoBitsPerSecond: 2_500_000,
    });
    recorder.addEventListener("dataavailable", (event) => {
      if (event.data.size > 0 && sessionId) {
        const pending = sendChunk(event.data, sessionId);
        pendingChunks.add(pending);
        void pending.then(
          () => pendingChunks.delete(pending),
          (error: unknown) => {
            chunkError = error;
            pendingChunks.delete(pending);
          },
        );
      }
    });
    recorder.addEventListener(
      "stop",
      () => {
        void releaseMedia().catch((error: unknown) => {
          chunkError = error;
        });
      },
      {
        once: true,
      },
    );
    recorder.start(4_000);
    stream.getVideoTracks().forEach((track) =>
      track.addEventListener(
        "ended",
        () => {
          if (recorder?.state === "recording") recorder.stop();
          void chrome.runtime
            .sendMessage({ type: "RECORDER_STOPPED" })
            .catch(() => undefined);
        },
        { once: true },
      ),
    );
    return { audio: stream.getAudioTracks().length > 0 };
  } catch (error) {
    await releaseMedia();
    recorder = undefined;
    throw error;
  }
}

function releaseMedia(): Promise<void> {
  stream?.getTracks().forEach((track) => track.stop());
  stream = undefined;
  const close = closeAudio;
  closeAudio = undefined;
  if (close) mediaRelease = close();
  return mediaRelease;
}

async function sendChunk(blob: Blob, captureSessionId: string): Promise<void> {
  const bytes = await blob.arrayBuffer();
  const response = await chrome.runtime.sendMessage({
    type: "RECORDER_CHUNK",
    sessionId: captureSessionId,
    bytesBase64: encodeMessageBytes(bytes),
    mimeType: blob.type,
  } satisfies ExtensionMessage);
  if (!response?.ok && recorder?.state === "recording") {
    recorder.stop();
  }
  if (!response?.ok) {
    throw new Error(String(response?.error ?? "recorder chunk upload failed"));
  }
}

async function stopRecording(): Promise<void> {
  if (!recorder || recorder.state === "inactive") {
    await releaseMedia();
    await Promise.all([...pendingChunks]);
    if (chunkError) throw chunkError;
    return;
  }
  await new Promise<void>((resolve) => {
    recorder?.addEventListener(
      "stop",
      () => {
        recorder = undefined;
        resolve();
      },
      { once: true },
    );
    recorder?.stop();
  });
  await releaseMedia();
  await Promise.all([...pendingChunks]);
  if (chunkError) {
    throw chunkError;
  }
}

function preferredMimeType(): string {
  for (const candidate of [
    "video/webm;codecs=vp9,opus",
    "video/webm;codecs=vp8,opus",
    "video/webm",
  ]) {
    if (MediaRecorder.isTypeSupported(candidate)) {
      return candidate;
    }
  }
  return "";
}
