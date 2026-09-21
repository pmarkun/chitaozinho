import { describe, expect, it } from "vitest";

import { isConstructionHost } from "./construction";

describe("public site routing", () => {
  it.each(["evidencias.org.br", "www.evidencias.org.br"])(
    "shows construction on %s",
    (hostname) => expect(isConstructionHost(hostname)).toBe(true),
  );

  it.each(["beta.evidencias.org.br", "127.0.0.1", "localhost"])(
    "keeps the beta application on %s",
    (hostname) => expect(isConstructionHost(hostname)).toBe(false),
  );
});
