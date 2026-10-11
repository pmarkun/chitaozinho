import {
  DOMAINS,
  base64UrlEncode,
  bytesToHex,
  canonicalBytes,
  sha256Identifier,
  signCanonicalWithKey,
} from "@chitaozinho/protocol";
import { BlobWriter, Uint8ArrayReader, ZipWriter } from "@zip.js/zip.js";
import { afterEach, describe, expect, it, vi } from "vitest";

import { type TrustRoot, verifyEvidencePackage } from "./validator";

describe("web evidence verifier", () => {
  afterEach(() => vi.unstubAllGlobals());

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

  it("trusts an operational key certified by an independent root", async () => {
    const fixture = await buildPackage({ rootCertified: true });

    const report = await verifyEvidencePackage({
      packageFile: fixture.file,
      trustedRoot: fixture.trustedRoot!,
    });

    expect(report.trustMode).toBe("root_certified");
    expect(report.checks.find((check) => check.id === "trust")?.status).toBe(
      "valid",
    );
  });

  it("recognizes both legacy and current methodology versions", async () => {
    for (const methodologyVersion of ["0.1", "0.2"] as const) {
      const fixture = await buildPackage({ methodologyVersion });
      const report = await verifyEvidencePackage({ packageFile: fixture.file });
      expect(
        report.checks.find((check) => check.id === "methodology")?.status,
      ).toBe("valid");
    }
  });

  it("looks up the temporal proof using only the session and manifest hash", async () => {
    const fixture = await buildPackage();
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ bundle_available: false, attestation_count: 0 }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    const report = await verifyEvidencePackage({
      packageFile: fixture.file,
      proofApiBaseUrl: "https://api.example.test/",
    });

    expect(report.temporalProof).toBe("pending");
    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(
      /^https:\/\/api\.example\.test\/v1\/public\/proofs\/synthetic-web-session\?manifest_hash=sha256%3A[0-9a-f]{64}$/,
    );
    expect(options.credentials).toBe("omit");
    expect(options.redirect).toBe("error");
    expect(
      report.checks.find((check) => check.id === "external_proofs")?.status,
    ).toBe("warning");
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

  describe("adversarial audit: regression guards", () => {
    it("rejects a duplicate unsigned index key without access to signing keys", async () => {
      const fixture = await buildPackage({ duplicateIndexSession: true });
      await expect(
        verifyEvidencePackage({
          packageFile: fixture.file,
          trustedServerKeyHex: fixture.serverPublicKeyHex,
        }),
      ).rejects.toThrow("JSON inválido");
    });

    it("rejects a complete claim despite a signed known gap", async () => {
      const fixture = await buildPackage({
        knownGaps: ["Main DOM unavailable"],
      });
      await expect(
        verifyEvidencePackage({
          packageFile: fixture.file,
          trustedServerKeyHex: fixture.serverPublicKeyHex,
        }),
      ).rejects.toThrow("Captura completa");
    });

    it("rejects an empty receipt chain for captured parts", async () => {
      const fixture = await buildPackage({ omitReceipts: true });
      await expect(
        verifyEvidencePackage({
          packageFile: fixture.file,
          trustedServerKeyHex: fixture.serverPublicKeyHex,
        }),
      ).rejects.toThrow("Recibo obrigatório ausente");
    });

    it("rejects a signed receipt that names another session", async () => {
      const fixture = await buildPackage({ receiptSession: "foreign-session" });
      await expect(
        verifyEvidencePackage({
          packageFile: fixture.file,
          trustedServerKeyHex: fixture.serverPublicKeyHex,
        }),
      ).rejects.toThrow("Sessão do recibo");
    });

    it("rejects root certification when an explicit operational anchor disagrees", async () => {
      const fixture = await buildPackage({ rootCertified: true });
      await expect(
        verifyEvidencePackage({
          packageFile: fixture.file,
          trustedRoot: fixture.trustedRoot!,
          trustedServerKeyHex: "00".repeat(32),
        }),
      ).rejects.toThrow("chave confiável");
    });

    it("accepts a matching explicit anchor along with root certification", async () => {
      const fixture = await buildPackage({ rootCertified: true });
      const report = await verifyEvidencePackage({
        packageFile: fixture.file,
        trustedRoot: fixture.trustedRoot!,
        trustedServerKeyHex: fixture.serverPublicKeyHex,
      });
      expect(report.trustMode).toBe("root_certified");
    });

    it("preserves explicitly incomplete captures with known gaps", async () => {
      const fixture = await buildPackage({
        knownGaps: ["Main DOM unavailable"],
        status: "incomplete",
      });
      const report = await verifyEvidencePackage({ packageFile: fixture.file });
      expect(report.result).toBe("integral_but_incomplete");
    });

    it("rejects complete captures with unavailable artifacts", async () => {
      const fixture = await buildPackage({ unavailableArtifact: true });
      await expect(
        verifyEvidencePackage({ packageFile: fixture.file }),
      ).rejects.toThrow("Captura completa");
    });

    it("preserves incomplete captures with unavailable artifacts", async () => {
      const fixture = await buildPackage({
        unavailableArtifact: true,
        status: "incomplete",
      });
      const report = await verifyEvidencePackage({ packageFile: fixture.file });
      expect(report.result).toBe("integral_but_incomplete");
    });

    it("does not assert valid custody when an event-only capture has no receipts", async () => {
      const fixture = await buildPackage({ noParts: true, omitReceipts: true });
      const report = await verifyEvidencePackage({ packageFile: fixture.file });
      expect(
        report.checks.find((check) => check.id === "receipt_chain")?.status,
      ).toBe("info");
    });

    it("rejects silently downgrading an explicitly required root", async () => {
      const fixture = await buildPackage();
      await expect(
        verifyEvidencePackage({
          packageFile: fixture.file,
          trustedRoot: {
            key_id: "required-root",
            algorithm: "Ed25519",
            public_key_hex: "00".repeat(32),
          },
        }),
      ).rejects.toThrow("raiz confiável");
    });

    it("rejects incomplete root delegation instead of falling back to self-declared trust", async () => {
      const fixture = await buildPackage({
        rootCertified: true,
        missingRevocationReference: true,
      });
      await expect(
        verifyEvidencePackage({ packageFile: fixture.file }),
      ).rejects.toThrow("Delegação pela raiz incompleta");
    });

    for (const receiptBinding of [
      "artifact_id",
      "part_number",
      "part_hash",
    ] as const) {
      it(`rejects correctly signed receipt with wrong ${receiptBinding}`, async () => {
        const fixture = await buildPackage({ receiptBinding });
        await expect(
          verifyEvidencePackage({ packageFile: fixture.file }),
        ).rejects.toThrow("Vínculo de recibo");
      });
    }

    it("rejects duplicate keys nested in signed JSONL", async () => {
      const fixture = await buildPackage({ duplicateEntryKey: true });
      await expect(
        verifyEvidencePackage({ packageFile: fixture.file }),
      ).rejects.toThrow("JSONL inválido");
    });

    it("accepts attacker-generated keys by default, with a trust warning", async () => {
      const fixture = await buildPackage();
      const report = await verifyEvidencePackage({ packageFile: fixture.file });
      expect(report.result).toBe("integral");
      expect(report.trustMode).toBe("self_declared");
      expect(report.checks.find((check) => check.id === "trust")?.status).toBe(
        "warning",
      );
      await expect(
        verifyEvidencePackage({
          packageFile: fixture.file,
          trustedServerKeyHex: "00".repeat(32),
        }),
      ).rejects.toThrow("chave confiável");
    });

    for (const unsignedMutation of [
      "artifact",
      "remove",
      "extra",
      "index",
      "signature",
      "client_key",
    ] as const) {
      it(`rejects post-signing mutation: ${unsignedMutation}`, async () => {
        const fixture = await buildPackage({ unsignedMutation });
        await expect(
          verifyEvidencePackage({
            packageFile: fixture.file,
            trustedServerKeyHex: fixture.serverPublicKeyHex,
          }),
        ).rejects.toThrow();
      });
    }
  });
});

async function buildPackage(
  options: {
    tamperMethodology?: boolean;
    unsafePath?: boolean;
    methodologyVersion?: "0.1" | "0.2";
    rootCertified?: boolean;
    missingRevocationReference?: boolean;
    duplicateIndexSession?: boolean;
    knownGaps?: string[];
    omitReceipts?: boolean;
    receiptSession?: string;
    receiptBinding?: "artifact_id" | "part_number" | "part_hash";
    duplicateEntryKey?: boolean;
    status?: "complete" | "incomplete";
    unavailableArtifact?: boolean;
    noParts?: boolean;
    unsignedMutation?:
      "artifact" | "remove" | "extra" | "index" | "signature" | "client_key";
  } = {},
): Promise<{
  file: File;
  checksum: File;
  serverPublicKeyHex: string;
  trustedRoot?: TrustRoot;
}> {
  const server = await generateKeyPair();
  const client = await generateKeyPair();
  const root = options.rootCertified ? await generateKeyPair() : undefined;
  const sessionId = "synthetic-web-session";
  const methodologyPath = `methodology/methodology-v${options.methodologyVersion ?? "0.1"}.md`;
  const entry = {
    protocol_version: "0.1.0",
    entry_type: options.noParts ? "capture_started" : "artifact_part",
    artifact_id: "note",
    part_number: 0,
    part_hash: sha256Identifier(encode("synthetic captured bytes")),
    session_id: sessionId,
    sequence: 0,
    previous_entry_hash: null,
    client_clock_id: "clock-1",
    client_monotonic_time: 0,
    client_wall_time: "2026-07-30T10:00:00-03:00",
    server_challenge: "c3ludGhldGlj",
  };
  if (options.noParts) {
    for (const field of ["artifact_id", "part_number", "part_hash"])
      delete (entry as Record<string, unknown>)[field];
  }
  const entryHash = sha256Identifier(canonicalBytes(entry));
  const entrySignature = await signCanonicalWithKey(
    DOMAINS.entry,
    entry,
    client.privateKey,
  );
  const receipt = {
    protocol_version: "0.1.0",
    session_id: options.receiptSession ?? sessionId,
    sequence: 0,
    entry_hash: entryHash,
    artifact_id: options.noParts ? null : "note",
    part_number: options.noParts ? null : 0,
    part_hash: options.noParts ? null : entry.part_hash,
    previous_receipt_hash: null,
    server_time: "2026-07-30T13:00:01Z",
    persistence_state: "durable_staging",
  };
  if (options.receiptBinding) {
    Object.assign(receipt, { [options.receiptBinding]: "forged" });
  }
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
  if (options.unavailableArtifact)
    Object.assign(artifact, {
      status: "unavailable",
      artifact_hash: undefined,
      reason: "Capture permission denied",
    });
  const close = {
    protocol_version: "0.1.0",
    session_id: sessionId,
    session_root: entryHash,
    last_entry_hash: entryHash,
    entry_count: 1,
    artifacts: [artifact],
    known_gaps: options.knownGaps ?? [],
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
    status: options.status ?? "complete",
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
  const serverRecord: Record<string, string> = {
    key_id: "server-synthetic",
    algorithm: "Ed25519",
    public_key_hex: bytesToHex(server.publicKey),
  };
  const trustMembers: [string, Uint8Array][] = [];
  if (root) {
    serverRecord.certificate_path = "signatures/server-key-certificate.json";
    serverRecord.revocation_list_path =
      "signatures/server-key-revocations.json";
    const certificateDocument = {
      schema_version: "0.1.0",
      key_id: "server-synthetic",
      algorithm: "Ed25519",
      public_key_hex: bytesToHex(server.publicKey),
      purpose: "server_signing",
      issuer_key_id: "root-synthetic",
      valid_from: "2026-07-01T00:00:00Z",
      valid_until: "2026-09-29T00:00:00Z",
    };
    const revocationDocument = {
      schema_version: "0.1.0",
      issuer_key_id: "root-synthetic",
      sequence: 1,
      issued_at: "2026-07-30T12:00:00Z",
      revoked_keys: [],
    };
    trustMembers.push(
      [
        serverRecord.certificate_path,
        canonicalBytes({
          document: certificateDocument,
          signature_hex: bytesToHex(
            await signCanonicalWithKey(
              DOMAINS.keyCertificate,
              certificateDocument,
              root.privateKey,
            ),
          ),
        }),
      ],
      [
        serverRecord.revocation_list_path,
        canonicalBytes({
          document: revocationDocument,
          signature_hex: bytesToHex(
            await signCanonicalWithKey(
              DOMAINS.keyRevocationList,
              revocationDocument,
              root.privateKey,
            ),
          ),
        }),
      ],
    );
  }
  if (options.missingRevocationReference)
    delete serverRecord.revocation_list_path;
  const members = new Map<string, Uint8Array>([
    ["README.txt", encode("Synthetic evidence package\n")],
    [
      methodologyPath,
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
      options.omitReceipts
        ? new Uint8Array()
        : line({
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
        server: serverRecord,
        client: {
          key_id: "client-synthetic",
          algorithm: "Ed25519",
          public_key_hex: bytesToHex(client.publicKey),
        },
      }),
    ],
    ...trustMembers,
  ]);
  if (options.duplicateEntryKey) {
    const original = new TextDecoder().decode(
      members.get("chain/entries.jsonl"),
    );
    members.set(
      "chain/entries.jsonl",
      encode(
        original.replace(
          '"entry":{',
          '"entry":{"session_id":"forged-first-value",',
        ),
      ),
    );
  }
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
      methodologyPath,
      encode("Changed after the package index was signed.\n"),
    );
  }
  // Everything below happens after signing, without using either private key.
  if (options.duplicateIndexSession) {
    const original = new TextDecoder().decode(
      members.get("package-index.json"),
    );
    members.set(
      "package-index.json",
      encode('{"session_id":"forged-first-value",' + original.slice(1)),
    );
  }
  switch (options.unsignedMutation) {
    case "artifact":
      members.set("capture/note.txt", encode("fabricated captured bytes"));
      break;
    case "remove":
      members.delete("capture/note.txt");
      break;
    case "extra":
      members.set("capture/unindexed.txt", encode("unindexed"));
      break;
    case "index":
      members.set(
        "package-index.json",
        canonicalBytes({ ...packageIndex, session_id: "forged" }),
      );
      break;
    case "signature":
      members.set(
        "signatures/package-index.server.sig",
        encode("00".repeat(64)),
      );
      break;
    case "client_key":
      members.set("signatures/public-keys.json", encode("{}"));
      break;
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
    ...(root
      ? {
          trustedRoot: {
            key_id: "root-synthetic",
            algorithm: "Ed25519" as const,
            public_key_hex: bytesToHex(root.publicKey),
          },
        }
      : {}),
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
