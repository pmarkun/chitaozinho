import { expect, test } from "vitest";

import { incrementalSha256Identifier, totalByteLength } from "./hash";

const encoder = new TextEncoder();

test("hashes multipart bytes incrementally without concatenating them", () => {
  const parts = ["original ", "webm ", "bytes"].map(
    (value) => encoder.encode(value).buffer,
  );

  expect(incrementalSha256Identifier(parts)).toBe(
    "sha256:0e53603f2d97efae19c970b853b4adc0ca74402e6cd762385b5480fafcd8df2c",
  );
  expect(totalByteLength(parts)).toBe(19);
});
