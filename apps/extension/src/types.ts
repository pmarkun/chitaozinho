export type CaptureStatus =
  | "starting"
  | "recording"
  | "finalizing"
  | "complete"
  | "interrupted"
  | "error";

export interface SessionRecord {
  id: string;
  challenge: string;
  keyId: string;
  publicKey: Uint8Array;
  privateKey: CryptoKey | null;
  clockId: string;
  clockStartedAt: number;
  nextSequence: number;
  previousEntryHash: string | null;
  tabId: number;
  windowId: number;
  startedAt: string;
  status: CaptureStatus;
  uploadedParts: number;
  durationMs: number;
  recordingActive: boolean;
  captureFinished: boolean;
  artifacts: ArtifactSummary[];
  packageHash?: string;
  error?: string;
}

export interface ArtifactSummary {
  artifact_id: string;
  path: string;
  size: number;
  status: "captured" | "unavailable" | "failed" | "not_requested";
  artifact_hash?: string;
  reason?: string;
}

export interface PartRecord {
  id: string;
  sessionId: string;
  artifactId: string;
  partNumber: number;
  bytes: ArrayBuffer;
  hash: string;
  entry: ChainEntry;
  entryHash: string;
  signatureHex: string;
  state: "pending" | "uploaded";
}

export interface ReceiptRecord {
  id: string;
  sessionId: string;
  artifactId: string;
  partNumber: number;
  receipt: Record<string, unknown>;
  receiptHash: string;
  receiptSignatureHex: string;
}

export interface ChainEntry {
  protocol_version: "0.1.0";
  entry_type: string;
  session_id: string;
  sequence: number;
  previous_entry_hash: string | null;
  client_clock_id: string;
  client_monotonic_time: number;
  client_wall_time: string;
  server_challenge: string;
  artifact_id?: string;
  part_number?: number;
  part_hash?: string;
  artifact_hash?: string;
  event_data?: Record<string, unknown>;
}

export interface ExtensionMessage {
  type:
    | "GET_STATE"
    | "DISMISS_RESULT"
    | "RESUME_CAPTURE"
    | "START_CAPTURE"
    | "STOP_CAPTURE"
    | "ADD_MARKER"
    | "ADD_SCREENSHOT"
    | "RECORDER_START"
    | "RECORDER_STOP"
    | "RECORDER_CHUNK"
    | "RECORDER_STOPPED"
    | "SCROLL";
  consent?: boolean;
  streamId?: string;
  sessionId?: string;
  bytes?: ArrayBuffer;
  mimeType?: string;
  note?: string;
  eventData?: Record<string, unknown>;
}
