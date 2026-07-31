import {
  DOMAINS,
  base64UrlEncode,
  bytesToHex,
  canonicalBytes,
  sha256Identifier,
  signCanonicalWithKey,
} from "@chitaozinho/protocol";
import { BlobWriter, Uint8ArrayReader, ZipWriter } from "@zip.js/zip.js";
import { describe, expect, it } from "vitest";

import { verifyEvidencePackage } from "./validator";

describe("web evidence verifier", () => {
  it("validates a signed package locally without network access", async () => {
    const fixture = await buildPackage();

    const report = await verifyEvidencePackage({
      packageFile: fixture.file,
      checksumFile: fixture.checksum,
      trustedServerKeyHex: fixture.serverPublicKeyHex,
    });

    expect(report.result).toBe("integral");
    expect(report.sessionId).toBe("synthetic-web-session");
    expect(report.trustMode).toBe("custom_operational_key");
    expect(report.temporalProof).toBe("not_provided");
    expect(report.checks.map((check) => check.id)).toContain("methodology");
  });

  it("labels packaged-only trust instead of claiming independent trust", async () => {
    const fixture = await buildPackage();

    const report = await verifyEvidencePackage({
      packageFile: fixture.file,
    });

    expect(report.trustMode).toBe("self_declared");
    expect(report.checks.find((check) => check.id === "trust")?.status).toBe(
      "warning",
    );
  });

  it("rejects changed indexed content and a wrong detached checksum", async () => {
    const changed = await buildPackage({ tamperMethodology: true });
    await expect(
      verifyEvidencePackage({ packageFile: changed.file }),
    ).rejects.toThrow("divergente: methodology/methodology-v0.1.md");

    const fixture = await buildPackage();
    const wrongChecksum = new File(
      [`${"0".repeat(64)}  evidence.zip\n`],
      "evidence.zip.sha256",
      { type: "text/plain" },
    );
    await expect(
      verifyEvidencePackage({
        packageFile: fixture.file,
        checksumFile: wrongChecksum,
      }),
    ).rejects.toThrow("checksum externo");
  });

  it("rejects unsafe archive paths before reading package content", async () => {
    const fixture = await buildPackage({ unsafePath: true });

    await expect(
      verifyEvidencePackage({ packageFile: fixture.file }),
    ).rejects.toThrow("Caminho inseguro");
  });
});

async function buildPackage(
  options: {
    tamperMethodology?: boolean;
    unsafePath?: boolean;
  } = {},
): Promise<{
  file: File;
  checksum: File;
  serverPublicKeyHex: string;
}> {
  const server = await generateKeyPair();
  const client = await generateKeyPair();
  const sessionId = "synthetic-web-session";
  const entry = {
    protocol_version: "0.1.0",
    entry_type: "capture_started",
    session_id: sessionId,
    sequence: 0,
    previous_entry_hash: null,
    client_clock_id: "clock-1",
    client_monotonic_time: 0,
    client_wall_time: "2026-07-30T10:00:00-03:00",
    server_challenge: "c3ludGhldGlj",
  };
  const entryHash = sha256Identifier(canonicalBytes(entry));
  const entrySignature = await signCanonicalWithKey(
    DOMAINS.entry,
    entry,
    client.privateKey,
  );
  const receipt = {
    protocol_version: "0.1.0",
    session_id: sessionId,
    sequence: 0,
    entry_hash: entryHash,
    artifact_id: null,
    part_number: null,
    part_hash: null,
    previous_receipt_hash: null,
    server_time: "2026-07-30T13:00:01Z",
    persistence_state: "durable_staging",
  };
  const receiptHash = sha256Identifier(canonicalBytes(receipt));
  const receiptSignature = await signCanonicalWithKey(
    DOMAINS.receipt,
    receipt,
    server.privateKey,
  );
  const artifactContent = encode("synthetic captured bytes");
  const artifact = {
    artifact_id: "note",
    path: "capture/note.txt",
    size: artifactContent.byteLength,
    status: "captured",
    artifact_hash: sha256Identifier(artifactContent),
  };
  const close = {
    protocol_version: "0.1.0",
    session_id: sessionId,
    session_root: entryHash,
    last_entry_hash: entryHash,
    entry_count: 1,
    artifacts: [artifact],
    known_gaps: [],
    client_key_id: "client-synthetic",
    client_public_key: base64UrlEncode(client.publicKey),
  };
  const closeSignature = await signCanonicalWithKey(
    DOMAINS.captureClose,
    close,
    client.privateKey,
  );
  const manifest = {
    schema_version: "0.1.0",
    session_id: sessionId,
    status: "complete",
    capture: {
      started_at_client: "2026-07-30T10:00:00-03:00",
      ended_at_client: "2026-07-30T10:01:00-03:00",
      started_at_server: "2026-07-30T13:00:00Z",
      ended_at_server: "2026-07-30T13:01:00Z",
      software: {
        name: "Synthetic fixture",
        version: "0.1.0",
        commit: "synthetic",
        build_hash: `sha256:${"1".repeat(64)}`,
      },
    },
    artifacts: [
      {
        ...artifact,
        media_type: "text/plain",
        method: "synthetic fixture",
        provenance: "client_reported",
      },
    ],
    chain: {
      first_hash: entryHash,
      last_hash: entryHash,
      entry_count: 1,
      root_hash: entryHash,
    },
    capture_close: {
      path: "chain/capture-close.json",
      client_signature_path: "signatures/capture-close.client.sig",
    },
    limitations: ["Synthetic test package."],
  };
  const manifestSignature = await signCanonicalWithKey(
    DOMAINS.manifest,
    manifest,
    server.privateKey,
  );
  const members = new Map<string, Uint8Array>([
    ["README.txt", encode("Synthetic evidence package\n")],
    [
      "methodology/methodology-v0.1.md",
      encode("Synthetic methodology processed locally in the browser.\n"),
    ],
    ["capture/note.txt", artifactContent],
    ["capture-manifest.json", canonicalBytes(manifest)],
    ["chain/capture-close.json", canonicalBytes(close)],
    [
      "chain/entries.jsonl",
      line({
        entry,
        entry_hash: entryHash,
        signature_hex: bytesToHex(entrySignature),
      }),
    ],
    [
      "chain/receipts.jsonl",
      line({
        receipt,
        receipt_hash: receiptHash,
        signature_hex: bytesToHex(receiptSignature),
      }),
    ],
    [
      "signatures/capture-close.client.sig",
      encode(`${bytesToHex(closeSignature)}\n`),
    ],
    [
      "signatures/capture-manifest.server.sig",
      encode(`${bytesToHex(manifestSignature)}\n`),
    ],
    [
      "signatures/public-keys.json",
      canonicalBytes({
        schema_version: "0.1.0",
        server: {
          key_id: "server-synthetic",
          algorithm: "Ed25519",
          public_key_hex: bytesToHex(server.publicKey),
        },
        client: {
          key_id: "client-synthetic",
          algorithm: "Ed25519",
          public_key_hex: bytesToHex(client.publicKey),
        },
      }),
    ],
  ]);
  const packageIndex = {
    schema_version: "0.1.0",
    session_id: sessionId,
    created_at: "2026-07-30T13:01:00Z",
    members: [...members.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([path, content]) => ({
        path,
        size: content.byteLength,
        media_type: mediaType(path),
        sha256: sha256Identifier(content),
      })),
  };
  members.set("package-index.json", canonicalBytes(packageIndex));
  members.set(
    "signatures/package-index.server.sig",
    encode(
      `${bytesToHex(
        await signCanonicalWithKey(
          DOMAINS.packageIndex,
          packageIndex,
          server.privateKey,
        ),
      )}\n`,
    ),
  );
  if (options.tamperMethodology) {
    members.set(
      "methodology/methodology-v0.1.md",
      encode("Changed after the package index was signed.\n"),
    );
  }

  const writer = new ZipWriter(new BlobWriter("application/zip"), {
    level: 0,
  });
  for (const [path, content] of [...members.entries()].sort(([left], [right]) =>
    left.localeCompare(right),
  )) {
    await writer.add(path, new Uint8ArrayReader(content));
  }
  if (options.unsafePath) {
    await writer.add("../escape.txt", new Uint8ArrayReader(encode("unsafe")));
  }
  const blob = await writer.close();
  const file = new File([blob], "evidence.zip", {
    type: "application/zip",
  });
  const digest = sha256Identifier(new Uint8Array(await file.arrayBuffer()));
  const checksum = new File(
    [`${digest.slice("sha256:".length)}  evidence.zip\n`],
    "evidence.zip.sha256",
    { type: "text/plain" },
  );
  return {
    file,
    checksum,
    serverPublicKeyHex: bytesToHex(server.publicKey),
  };
}

async function generateKeyPair(): Promise<{
  privateKey: CryptoKey;
  publicKey: Uint8Array;
}> {
  const pair = (await crypto.subtle.generateKey("Ed25519", true, [
    "sign",
    "verify",
  ])) as CryptoKeyPair;
  return {
    privateKey: pair.privateKey,
    publicKey: new Uint8Array(
      await crypto.subtle.exportKey("raw", pair.publicKey),
    ),
  };
}

function line(value: unknown): Uint8Array {
  const content = canonicalBytes(value);
  const result = new Uint8Array(content.byteLength + 1);
  result.set(content);
  result[result.length - 1] = 0x0a;
  return result;
}

function encode(value: string): Uint8Array {
  return new TextEncoder().encode(value);
}

function mediaType(path: string): string {
  if (path.endsWith(".json")) return "application/json";
  if (path.endsWith(".jsonl")) return "application/x-ndjson";
  if (path.endsWith(".sig")) return "application/octet-stream";
  if (path.endsWith(".md")) return "text/markdown";
  return "text/plain";
}
