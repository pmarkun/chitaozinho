import { describe, expect, it } from "vitest";

import english from "../public/_locales/en/messages.json";
import brazilianPortuguese from "../public/_locales/pt_BR/messages.json";

describe("extension locales", () => {
  it("keeps complete and equivalent pt-BR and English catalogs", () => {
    expect(Object.keys(english).sort()).toEqual(
      Object.keys(brazilianPortuguese).sort(),
    );
    for (const catalog of [english, brazilianPortuguese]) {
      expect(
        Object.values(catalog).every(
          ({ message }) => message.trim().length > 0,
        ),
      ).toBe(true);
    }
  });
});
