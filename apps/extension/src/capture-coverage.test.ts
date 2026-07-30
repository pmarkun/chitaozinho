import { describe, expect, it } from "vitest";

import { describeCaptureCoverage } from "./capture-coverage";

describe("capture coverage", () => {
  it("describes iframe, canvas, WebGL and protected media limitations", () => {
    const coverage = describeCaptureCoverage({
      scriptingAccess: true,
      iframeTotal: 3,
      iframeSameOriginAccessible: 1,
      canvasTotal: 2,
      protectedMediaTotal: 1,
    });

    expect(coverage.iframes).toMatchObject({
      total: 3,
      same_origin_accessible: 1,
      coverage: "partial",
    });
    expect(coverage.canvas.coverage).toBe("visual_only");
    expect(coverage.webgl).toEqual({
      coverage: "visual_only",
      detection: "included with canvas; WebGL contexts are not introspected",
    });
    expect(coverage.protected_media).toMatchObject({
      eme_elements_detected: 1,
      coverage: "unavailable",
    });
    expect(coverage.limitations).toHaveLength(2);
  });

  it("marks protected browser pages unavailable without overstating coverage", () => {
    const coverage = describeCaptureCoverage({
      scriptingAccess: false,
      iframeTotal: null,
      iframeSameOriginAccessible: null,
      canvasTotal: null,
      protectedMediaTotal: null,
    });

    expect(coverage.top_level_dom.coverage).toBe("unavailable");
    expect(coverage.iframes.coverage).toBe("unavailable");
    expect(coverage.canvas.coverage).toBe("unavailable");
    expect(coverage.protected_media.coverage).toBe("unavailable");
    expect(coverage.limitations).toEqual([
      "top-level DOM unavailable: browser denied scripting access; visual artifacts remain best effort",
    ]);
  });

  it("keeps iframe capture visual-only even when same-origin access is possible", () => {
    const coverage = describeCaptureCoverage({
      scriptingAccess: true,
      iframeTotal: 1,
      iframeSameOriginAccessible: 1,
      canvasTotal: 0,
      protectedMediaTotal: 0,
    });

    expect(coverage.iframes.coverage).toBe("visual_only");
    expect(coverage.canvas.coverage).toBe("not_detected");
    expect(coverage.protected_media.coverage).toBe("not_detected");
    expect(coverage.limitations).toEqual([
      "iframe content partial: 1 of 1 frames same-origin accessible; nested documents are not serialized and viewport pixels remain visual best effort",
    ]);
  });
});
