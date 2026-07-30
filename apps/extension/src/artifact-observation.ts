export interface ArtifactObservation {
  method: string;
  provenance: "client_reported";
  permissions: string[];
  capture_interval: {
    started_at_client: string;
    ended_at_client: string;
  };
  completeness: "complete" | "unavailable";
}

export function artifactObservation(
  method: string,
  permissions: string[],
  startedAt: string,
  endedAt: string,
  completeness: ArtifactObservation["completeness"],
): ArtifactObservation {
  return {
    method,
    provenance: "client_reported",
    permissions: [...new Set(permissions)].sort(),
    capture_interval: {
      started_at_client: startedAt,
      ended_at_client: endedAt,
    },
    completeness,
  };
}
