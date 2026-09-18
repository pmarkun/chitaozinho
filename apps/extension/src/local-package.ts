import {
  BlobReader,
  BlobWriter,
  ZipWriter,
  configure,
} from "@zip.js/zip.js/index-native.js";
import { sha256 } from "@noble/hashes/sha2.js";
import {
  base64UrlDecode,
  bytesToHex,
  DOMAINS,
  hexToBytes,
  sha256Identifier,
  verifyCanonical,
} from "@chitaozinho/protocol";
import { getLocalPackage, saveLocalPackage, sessionParts } from "./db";
import { incrementalSha256Identifier, totalByteLength } from "./hash";
import type { LocalPackageTemplate, PartRecord } from "./types";

configure({ useWebWorkers: false });

export async function assembleLocalPackage(
  template: LocalPackageTemplate,
  parts: PartRecord[],
): Promise<Blob> {
  if (template.evidence_mode !== "hash_only")
    throw new Error("invalid custody mode");
  const members = new Map<string, Blob>();
  for (const [path, encoded] of Object.entries(template.members)) {
    members.set(path, new Blob([new Uint8Array(base64UrlDecode(encoded))]));
  }
  const index = JSON.parse(await members.get("package-index.json")!.text()) as {
    session_id: string;
    members: { path: string; size: number; sha256: string }[];
  };
  const keys = JSON.parse(
    await members.get("signatures/public-keys.json")!.text(),
  );
  const signature = hexToBytes(
    (await members.get("signatures/package-index.server.sig")!.text()).trim(),
  );
  if (
    index.session_id !== template.session_id ||
    !(await verifyCanonical(
      DOMAINS.packageIndex,
      index,
      signature,
      hexToBytes(keys.server.public_key_hex),
    ))
  ) {
    throw new Error("invalid local package index signature");
  }
  for (const artifact of template.artifacts) {
    if (members.has(artifact.path)) throw new Error("duplicate package member");
    const records = parts
      .filter(
        (part) =>
          part.sessionId === template.session_id &&
          part.artifactId === artifact.artifact_id,
      )
      .sort((a, b) => a.partNumber - b.partNumber);
    if (
      !records.length ||
      records.some(
        (part, i) =>
          part.partNumber !== i ||
          part.hash !== sha256Identifier(new Uint8Array(part.bytes)),
      )
    ) {
      throw new Error("missing or modified local evidence parts");
    }
    const bytes = records.map((part) => part.bytes);
    if (
      totalByteLength(bytes) !== artifact.size ||
      incrementalSha256Identifier(bytes) !== artifact.sha256
    )
      throw new Error("local artifact hash mismatch");
    members.set(artifact.path, new Blob(bytes));
  }
  const indexed = new Set<string>();
  let total = 0;
  for (const member of index.members) {
    if (
      indexed.has(member.path) ||
      member.path === "package-index.json" ||
      member.path === "signatures/package-index.server.sig"
    )
      throw new Error("invalid index member");
    indexed.add(member.path);
    const blob = members.get(member.path);
    if (
      !blob ||
      blob.size !== member.size ||
      (await hashBlob(blob)) !== member.sha256
    )
      throw new Error("package member integrity mismatch");
    total += blob.size;
  }
  if (total > 1024 * 1024 * 1024 || members.size !== indexed.size + 2)
    throw new Error("unsupported local package size or members");
  const writer = new ZipWriter(new BlobWriter("application/zip"));
  for (const [path, blob] of [...members].sort(([a], [b]) =>
    a < b ? -1 : a > b ? 1 : 0,
  )) {
    if (
      path.startsWith("/") ||
      path.includes("\\") ||
      path.split("/").some((p) => !p || p === "." || p === "..")
    )
      throw new Error("unsafe package path");
    await writer.add(path, new BlobReader(blob), {
      level: 0,
      lastModDate: new Date("1980-01-01T00:00:00Z"),
      extendedTimestamp: false,
    });
  }
  return writer.close();
}

export async function hashBlob(blob: Blob): Promise<string> {
  const digest = sha256.create();
  for (let start = 0; start < blob.size; start += 1024 * 1024) {
    digest.update(
      new Uint8Array(
        await blob.slice(start, start + 1024 * 1024).arrayBuffer(),
      ),
    );
  }
  return `sha256:${bytesToHex(digest.digest())}`;
}

export async function localPackageUrls(
  sessionId: string,
  template?: LocalPackageTemplate,
) {
  let cached = await getLocalPackage(sessionId);
  if (!cached) {
    if (!template || template.session_id !== sessionId)
      throw new Error("package template unavailable");
    const blob = await assembleLocalPackage(
      template,
      await sessionParts(sessionId),
    );
    const hash = await hashBlob(blob);
    await saveLocalPackage(sessionId, blob, hash);
    cached = { sessionId, blob, hash };
  }
  return {
    packageUrl: URL.createObjectURL(cached.blob),
    checksumUrl: URL.createObjectURL(
      new Blob([`${cached.hash.slice(7)}  evidencias-${sessionId}.zip\n`], {
        type: "text/plain",
      }),
    ),
    packageHash: cached.hash,
    storageStatus: "hash_only",
  };
}
