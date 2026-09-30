import { afterEach, expect, it, vi } from "vitest";
import { captureConstraints, selectCaptureStream } from "./capture-source";
afterEach(() => vi.unstubAllGlobals());
it("does not request an audio track without the picker permission", () => {
  expect(captureConstraints("desktop", "id", false).audio).toBe(false);
  expect(captureConstraints("tab", "id", true).audio).toEqual({
    mandatory: { chromeMediaSource: "tab", chromeMediaSourceId: "id" },
  });
});
it("keeps the existing tab capture path", async () => {
  const getMediaStreamId = vi.fn().mockResolvedValue("tab-id");
  vi.stubGlobal("chrome", { tabCapture: { getMediaStreamId } });
  expect(await selectCaptureStream("tab", 42)).toEqual({
    streamId: "tab-id",
    source: "tab",
    audio: true,
  });
  expect(getMediaStreamId).toHaveBeenCalledWith({ targetTabId: 42 });
});
it.each([true, false])("propagates desktop audio choice %s", async (audio) => {
  vi.stubGlobal("chrome", {
    runtime: {},
    desktopCapture: {
      chooseDesktopMedia: (
        _: unknown,
        callback: (
          id: string,
          options: { canRequestAudioTrack: boolean },
        ) => void,
      ) => callback("desktop-id", { canRequestAudioTrack: audio }),
    },
  });
  expect(await selectCaptureStream("desktop", 42)).toEqual({
    streamId: "desktop-id",
    source: "desktop",
    audio,
  });
});
it("rejects cancellation instead of silently capturing a browser tab", async () => {
  vi.stubGlobal("chrome", {
    runtime: {},
    desktopCapture: {
      chooseDesktopMedia: (_: unknown, callback: (id: string) => void) =>
        callback(""),
    },
  });
  await expect(selectCaptureStream("desktop", 42)).rejects.toThrow("cancelled");
});
