import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const css = readFileSync(new URL("./popup.css", import.meta.url), "utf8");

describe("popup accessibility guards", () => {
  it("keeps normal text and focus indicators above WCAG AA contrast", () => {
    const pairs: Array<[string, string, number]> = [
      ["--text", "--page-background", 4.5],
      ["--body-text", "--page-background", 4.5],
      ["--muted-text", "--page-background", 4.5],
      ["--solid-text", "--brand", 4.5],
      ["--secondary-text", "--secondary-background", 4.5],
      ["--solid-text", "--danger", 4.5],
      ["--error", "--page-background", 4.5],
      ["--focus-ring", "--page-background", 3],
      ["--focus-ring", "--surface", 3],
      ["--focus-ring", "--secondary-background", 3],
    ];

    for (const [foreground, background, minimum] of pairs) {
      expect(
        contrastRatio(cssColor(foreground), cssColor(background)),
        `${foreground} on ${background}`,
      ).toBeGreaterThanOrEqual(minimum);
    }
  });

  it("supports a 320 CSS pixel viewport and visible keyboard focus", () => {
    expect(css).toMatch(/width:\s*360px;\s*max-width:\s*100vw;/);
    expect(css).toMatch(
      /outline:\s*3px solid var\(--focus-ring\);\s*outline-offset:\s*2px;/,
    );
  });
});

function cssColor(name: string): string {
  const match = css.match(
    new RegExp(`${name.replaceAll("-", "\\-")}:\\s*(#[0-9a-fA-F]{6})`),
  );
  if (!match) throw new Error(`CSS color ${name} not found`);
  return match[1];
}

function contrastRatio(foreground: string, background: string): number {
  const first = luminance(foreground);
  const second = luminance(background);
  return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
}

function luminance(color: string): number {
  const channels = [1, 3, 5].map((offset) => {
    const encoded = Number.parseInt(color.slice(offset, offset + 2), 16) / 255;
    return encoded <= 0.04045
      ? encoded / 12.92
      : ((encoded + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}
