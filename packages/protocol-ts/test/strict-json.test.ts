import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "vitest";
import { parseStrictJson } from "../src/index.js";

const vectors = JSON.parse(
  readFileSync(
    resolve(process.cwd(), "../../test-vectors/strict-json.json"),
    "utf8",
  ),
) as { name: string; json: string; valid: boolean }[];
for (const vector of vectors) {
  test(vector.name, () => {
    if (vector.valid)
      expect(parseStrictJson(vector.json)).toEqual(JSON.parse(vector.json));
    else expect(() => parseStrictJson(vector.json)).toThrow();
  });
}
test("bounds nesting before JSON parsing", () => {
  expect(() =>
    parseStrictJson("[".repeat(65) + "0" + "]".repeat(65)),
  ).toThrow();
});
