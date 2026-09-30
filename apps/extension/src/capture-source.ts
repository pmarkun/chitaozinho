export type CaptureSource = "tab" | "desktop";

export async function selectCaptureStream(
  source: CaptureSource,
  tabId: number,
) {
  if (source === "tab") {
    return {
      streamId: await chrome.tabCapture.getMediaStreamId({
        targetTabId: tabId,
      }),
      source,
      audio: true,
    };
  }
  return new Promise<{
    streamId: string;
    source: CaptureSource;
    audio: boolean;
  }>((resolve, reject) => {
    chrome.desktopCapture.chooseDesktopMedia(
      ["screen", "window", "audio"],
      (streamId, options) => {
        const error = chrome.runtime.lastError;
        if (error || !streamId) {
          reject(
            new Error(
              error?.message ??
                "Screen selection cancelled. No recording started.",
            ),
          );
        } else {
          resolve({ streamId, source, audio: options.canRequestAudioTrack });
        }
      },
    );
  });
}

export function captureConstraints(
  source: CaptureSource,
  streamId: string,
  audio: boolean,
): MediaStreamConstraints {
  const track = {
    mandatory: {
      chromeMediaSource: source === "desktop" ? "desktop" : "tab",
      chromeMediaSourceId: streamId,
    },
  } as MediaTrackConstraints;
  return { video: track, audio: audio ? track : false };
}
