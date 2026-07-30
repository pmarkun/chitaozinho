import { describe, expect, it } from "vitest";

import { artifactObservation } from "./artifact-observation";

describe("artifact observation", () => {
  it("records deterministic permissions, interval and completeness", () => {
    expect(
      artifactObservation(
        "MediaRecorder",
        ["tabCapture", "offscreen", "tabCapture"],
        "2026-07-30T15:00:00.000Z",
        "2026-07-30T15:01:00.000Z",
        "complete",
      ),
    ).toEqual({
      method: "MediaRecorder",
      provenance: "client_reported",
      permissions: ["offscreen", "tabCapture"],
      capture_interval: {
        started_at_client: "2026-07-30T15:00:00.000Z",
        ended_at_client: "2026-07-30T15:01:00.000Z",
      },
      completeness: "complete",
    });
  });
});
