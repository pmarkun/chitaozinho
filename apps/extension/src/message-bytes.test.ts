import { describe, expect, it } from "vitest";

import { decodeMessageBytes, encodeMessageBytes } from "./message-bytes";

describe("extension message bytes", () => {
  it("survive Chrome's JSON message serialization", () => {
    const original = new Uint8Array([0, 1, 2, 127, 128, 254, 255]);
    const transported = JSON.parse(
      JSON.stringify({ bytesBase64: encodeMessageBytes(original.buffer) }),
    ) as { bytesBase64: string };

    expect(new Uint8Array(decodeMessageBytes(transported.bytesBase64))).toEqual(
      original,
    );
  });
});
