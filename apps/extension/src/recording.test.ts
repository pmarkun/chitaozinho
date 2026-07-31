import { describe, expect, it } from "vitest";

import { preferredRecordingMimeType, VIDEO_BITS_PER_SECOND } from "./recording";

describe("recording profile", () => {
  it("prefers the lower-cost VP8 codec when supported", () => {
    const supported = new Set([
      "video/webm;codecs=vp8,opus",
      "video/webm;codecs=vp9,opus",
    ]);

    expect(preferredRecordingMimeType((value) => supported.has(value))).toBe(
      "video/webm;codecs=vp8,opus",
    );
    expect(VIDEO_BITS_PER_SECOND).toBe(2_000_000);
  });

  it("falls back without producing an unsupported MIME type", () => {
    expect(
      preferredRecordingMimeType(
        (value) => value === "video/webm;codecs=vp9,opus",
      ),
    ).toBe("video/webm;codecs=vp9,opus");
    expect(preferredRecordingMimeType(() => false)).toBe("");
  });
});
