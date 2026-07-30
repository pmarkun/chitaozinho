export interface PageFeatureInventory {
  scriptingAccess: boolean;
  iframeTotal: number | null;
  iframeSameOriginAccessible: number | null;
  canvasTotal: number | null;
  protectedMediaTotal: number | null;
}

export interface CaptureCoverage {
  top_level_dom: {
    coverage: "captured" | "unavailable";
  };
  iframes: {
    total: number | null;
    same_origin_accessible: number | null;
    coverage: "visual_only" | "partial" | "not_detected" | "unavailable";
    method: "visible viewport pixels; nested documents are not serialized";
  };
  canvas: {
    total: number | null;
    coverage: "visual_only" | "not_detected" | "unavailable";
    method: "visible viewport pixels; backing buffers are not serialized";
  };
  webgl: {
    coverage: "visual_only" | "unavailable";
    detection: "included with canvas; WebGL contexts are not introspected";
  };
  protected_media: {
    eme_elements_detected: number | null;
    coverage: "unavailable" | "not_detected";
    method: "MediaKeys presence; decrypted media is never extracted";
  };
  limitations: string[];
}

export function describeCaptureCoverage(
  inventory: PageFeatureInventory,
): CaptureCoverage {
  if (!inventory.scriptingAccess) {
    return {
      top_level_dom: { coverage: "unavailable" },
      iframes: {
        total: null,
        same_origin_accessible: null,
        coverage: "unavailable",
        method: "visible viewport pixels; nested documents are not serialized",
      },
      canvas: {
        total: null,
        coverage: "unavailable",
        method: "visible viewport pixels; backing buffers are not serialized",
      },
      webgl: {
        coverage: "unavailable",
        detection: "included with canvas; WebGL contexts are not introspected",
      },
      protected_media: {
        eme_elements_detected: null,
        coverage: "unavailable",
        method: "MediaKeys presence; decrypted media is never extracted",
      },
      limitations: [
        "top-level DOM unavailable: browser denied scripting access; visual artifacts remain best effort",
      ],
    };
  }

  const iframeTotal = inventory.iframeTotal ?? 0;
  const iframeAccessible = inventory.iframeSameOriginAccessible ?? 0;
  const canvasTotal = inventory.canvasTotal ?? 0;
  const protectedMediaTotal = inventory.protectedMediaTotal ?? 0;
  const limitations: string[] = [];

  if (iframeTotal > 0) {
    limitations.push(
      `iframe content partial: ${iframeAccessible} of ${iframeTotal} frames same-origin accessible; nested documents are not serialized and viewport pixels remain visual best effort`,
    );
  }
  if (protectedMediaTotal > 0) {
    limitations.push(
      `protected media unavailable: ${protectedMediaTotal} EME media elements detected; decrypted content is not asserted`,
    );
  }

  return {
    top_level_dom: { coverage: "captured" },
    iframes: {
      total: iframeTotal,
      same_origin_accessible: iframeAccessible,
      coverage:
        iframeTotal === 0
          ? "not_detected"
          : iframeAccessible === iframeTotal
            ? "visual_only"
            : "partial",
      method: "visible viewport pixels; nested documents are not serialized",
    },
    canvas: {
      total: canvasTotal,
      coverage: canvasTotal === 0 ? "not_detected" : "visual_only",
      method: "visible viewport pixels; backing buffers are not serialized",
    },
    webgl: {
      coverage: "visual_only",
      detection: "included with canvas; WebGL contexts are not introspected",
    },
    protected_media: {
      eme_elements_detected: protectedMediaTotal,
      coverage: protectedMediaTotal > 0 ? "unavailable" : "not_detected",
      method: "MediaKeys presence; decrypted media is never extracted",
    },
    limitations,
  };
}
