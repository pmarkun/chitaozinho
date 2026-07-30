import type { ExtensionMessage } from "./types";

let recorder: MediaRecorder | undefined;
let stream: MediaStream | undefined;
let sessionId: string | undefined;

chrome.runtime.onMessage.addListener(
  (
    message: ExtensionMessage,
    _sender,
    sendResponse: (value?: unknown) => void,
  ) => {
    if (
      message.type === "RECORDER_START" &&
      message.streamId &&
      message.sessionId
    ) {
      void startRecording(message.streamId, message.sessionId)
        .then(() => sendResponse({ ok: true }))
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
): Promise<void> {
  if (recorder?.state === "recording") {
    throw new Error("recorder is already active");
  }
  sessionId = captureSessionId;
  stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      mandatory: {
        chromeMediaSource: "tab",
        chromeMediaSourceId: streamId,
      },
    } as MediaTrackConstraints,
    video: {
      mandatory: {
        chromeMediaSource: "tab",
        chromeMediaSourceId: streamId,
      },
    } as MediaTrackConstraints,
  });
  recorder = new MediaRecorder(stream, {
    mimeType: preferredMimeType(),
    videoBitsPerSecond: 2_500_000,
  });
  recorder.addEventListener("dataavailable", (event) => {
    if (event.data.size > 0 && sessionId) {
      void sendChunk(event.data, sessionId);
    }
  });
  recorder.start(4_000);
}

async function sendChunk(blob: Blob, captureSessionId: string): Promise<void> {
  const bytes = await blob.arrayBuffer();
  const response = await chrome.runtime.sendMessage({
    type: "RECORDER_CHUNK",
    sessionId: captureSessionId,
    bytes,
    mimeType: blob.type,
  } satisfies ExtensionMessage);
  if (!response?.ok && recorder?.state === "recording") {
    recorder.stop();
  }
}

async function stopRecording(): Promise<void> {
  if (!recorder || recorder.state === "inactive") {
    return;
  }
  await new Promise<void>((resolve) => {
    recorder?.addEventListener(
      "stop",
      () => {
        stream?.getTracks().forEach((track) => track.stop());
        recorder = undefined;
        stream = undefined;
        resolve();
      },
      { once: true },
    );
    recorder?.stop();
  });
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
