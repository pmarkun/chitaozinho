import { sha256 } from "@noble/hashes/sha2.js";
import {
  DOMAINS,
  bytesToHex,
  canonicalBytes,
  hexToBytes,
  sha256Identifier,
  verifyCanonical,
} from "@chitaozinho/protocol";
import {
  BlobReader,
  BlobWriter,
  type FileEntry,
  ZipReader,
  configure,
} from "@zip.js/zip.js";

const MAX_ENTRIES = 10_000;
const MAX_FILE_SIZE = 512 * 1024 * 1024;
const MAX_TOTAL_SIZE = 1024 * 1024 * 1024;
const MAX_COMPRESSION_RATIO = 1_000;
const MAX_METADATA_SIZE = 16 * 1024 * 1024;
const MAX_JSON_DEPTH = 64;
const decoder = new TextDecoder("utf-8", { fatal: true });

configure({ useWebWorkers: false });

const PACKAGE_INDEX_PATH = "package-index.json";
const PACKAGE_INDEX_SIGNATURE_PATH = "signatures/package-index.server.sig";
const MANIFEST_PATH = "capture-manifest.json";
const MANIFEST_SIGNATURE_PATH = "signatures/capture-manifest.server.sig";
const PUBLIC_KEYS_PATH = "signatures/public-keys.json";
const ENTRIES_PATH = "chain/entries.jsonl";
const RECEIPTS_PATH = "chain/receipts.jsonl";
const PROOF_INDEX_PATH = "proof-bundle-index.json";
const PROOF_INDEX_SIGNATURE_PATH = "signatures/proof-bundle-index.server.sig";
const ATTESTATIONS_PATH = "attestations.jsonl";

export type CheckStatus = "valid" | "warning";

export interface VerificationCheck {
  id: string;
  label: string;
  status: CheckStatus;
  detail: string;
}

export interface VerificationReport {
  result: "integral" | "integral_but_incomplete";
  sessionId: string;
  packageHash: string;
  membersVerified: number;
  temporalProof: "not_provided" | "pending" | "signed_claims_only";
  attestationsVerified: number;
  trustMode: "self_declared" | "custom_operational_key";
  checks: VerificationCheck[];
}

export interface VerificationInput {
  packageFile: File;
  checksumFile?: File;
  proofBundleFile?: File;
  trustedServerKeyHex?: string;
}

interface Archive {
  entries: Map<string, FileEntry>;
  read(path: string): Promise<Uint8Array>;
  close(): Promise<void>;
}

interface PackageMember {
  path: string;
  size: number;
  media_type: string;
  sha256: string;
}

interface PackageIndex {
  schema_version: string;
  session_id: string;
  members: PackageMember[];
}

interface KeyRecord {
  key_id: string;
  algorithm: string;
  public_key_hex: string;
}

interface PublicKeys {
  schema_version: string;
  server: KeyRecord;
  client: KeyRecord;
}

interface ManifestArtifact {
  artifact_id: string;
  path: string;
  size: number;
  status: string;
  artifact_hash?: string;
  reason?: string;
}

interface CaptureManifest {
  schema_version: string;
  session_id: string;
  status: string;
  artifacts: ManifestArtifact[];
  chain: {
    first_hash: string;
    last_hash: string;
    entry_count: number;
    root_hash: string;
  };
  capture_close: {
    path: string;
    client_signature_path: string;
  };
}

interface ChainRecord {
  entry: Record<string, unknown>;
  entry_hash: string;
  signature_hex: string;
}

interface ReceiptRecord {
  receipt: Record<string, unknown>;
  receipt_hash: string;
  signature_hex: string;
}

export class EvidenceValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "EvidenceValidationError";
  }
}

export async function verifyEvidencePackage(
  input: VerificationInput,
): Promise<VerificationReport> {
  const packageHash = await hashFile(input.packageFile);
  const checks: VerificationCheck[] = [];
  if (input.checksumFile) {
    const checksum = (await input.checksumFile.text()).trim().split(/\s+/u)[0];
    ensure(
      checksum === packageHash.slice("sha256:".length),
      "O checksum externo não corresponde ao ZIP principal.",
    );
    checks.push(
      valid(
        "external_checksum",
        "Checksum externo",
        "O arquivo .sha256 corresponde ao ZIP selecionado.",
      ),
    );
  }

  const archive = await openArchive(input.packageFile);
  try {
    checks.push(
      valid(
        "safe_zip_structure",
        "Estrutura segura",
        "Caminhos, duplicações, links e limites do ZIP são válidos.",
      ),
    );
    const packageIndex = await readJson<PackageIndex>(
      archive,
      PACKAGE_INDEX_PATH,
    );
    validatePackageIndex(packageIndex);
    const publicKeys = await readJson<PublicKeys>(archive, PUBLIC_KEYS_PATH);
    validatePublicKeys(publicKeys);
    const serverKey = hexToBytes(publicKeys.server.public_key_hex);
    const clientKey = hexToBytes(publicKeys.client.public_key_hex);
    const trustMode = validateOperationalTrust(
      input.trustedServerKeyHex,
      serverKey,
    );
    const indexSignature = await readHex(
      archive,
      PACKAGE_INDEX_SIGNATURE_PATH,
      64,
    );
    ensure(
      await verifyCanonical(
        DOMAINS.packageIndex,
        packageIndex,
        indexSignature,
        serverKey,
      ),
      "A assinatura do índice do pacote é inválida.",
    );
    checks.push(
      valid(
        "package_index_signature",
        "Índice assinado",
        "A assinatura Ed25519 do índice é válida.",
      ),
    );

    await verifyIndexedMembers(
      archive,
      packageIndex.members,
      new Set([PACKAGE_INDEX_PATH, PACKAGE_INDEX_SIGNATURE_PATH]),
    );
    checks.push(
      valid(
        "member_hashes",
        "Arquivos do pacote",
        `${packageIndex.members.length} membros correspondem ao índice assinado.`,
      ),
    );

    const manifest = await readJson<CaptureManifest>(archive, MANIFEST_PATH);
    validateManifest(manifest, packageIndex);
    const manifestSignature = await readHex(
      archive,
      MANIFEST_SIGNATURE_PATH,
      64,
    );
    ensure(
      await verifyCanonical(
        DOMAINS.manifest,
        manifest,
        manifestSignature,
        serverKey,
      ),
      "A assinatura do manifesto é inválida.",
    );
    checks.push(
      valid(
        "manifest_signature",
        "Manifesto assinado",
        "O manifesto corresponde à assinatura do servidor.",
      ),
    );

    await verifyArtifacts(archive, manifest);
    checks.push(
      valid(
        "artifact_hashes",
        "Artefatos capturados",
        "Tamanhos e hashes dos artefatos presentes são válidos.",
      ),
    );
    const entries = await verifyEntryChain(archive, manifest, clientKey);
    checks.push(
      valid(
        "entry_chain",
        "Cadeia da captura",
        `${entries.size} eventos estão íntegros, ordenados e assinados.`,
      ),
    );
    const receiptCount = await verifyReceiptChain(archive, entries, serverKey);
    checks.push(
      valid(
        "receipt_chain",
        "Recibos do servidor",
        `${receiptCount} recibos estão íntegros e assinados.`,
      ),
    );
    await verifyCaptureClose(archive, manifest, publicKeys, clientKey);
    checks.push(
      valid(
        "capture_close_signature",
        "Encerramento da captura",
        "A declaração final do cliente corresponde ao manifesto.",
      ),
    );

    const methodologyPresent = [...archive.entries.keys()].some((path) =>
      /^methodology\/methodology-v\d+\.\d+\.md$/.test(path),
    );
    checks.push(
      methodologyPresent
        ? valid(
            "methodology",
            "Metodologia",
            "A metodologia versionada está coberta pelo índice assinado.",
          )
        : warning(
            "methodology",
            "Metodologia",
            "Este pacote é anterior à incorporação da metodologia versionada.",
          ),
    );

    let temporalProof: VerificationReport["temporalProof"] = "not_provided";
    let attestationsVerified = 0;
    if (input.proofBundleFile) {
      const proof = await verifyProofBundle(
        input.proofBundleFile,
        manifest,
        serverKey,
      );
      temporalProof = proof.temporalProof;
      attestationsVerified = proof.attestationsVerified;
      checks.push(...proof.checks);
    } else {
      checks.push(
        warning(
          "external_proofs",
          "Provas temporais",
          "Nenhum complemento probatório foi fornecido.",
        ),
      );
    }

    checks.push(
      trustMode === "custom_operational_key"
        ? valid(
            "trust",
            "Confiança da chave",
            "A chave operacional corresponde à chave informada separadamente.",
          )
        : warning(
            "trust",
            "Confiança da chave",
            "A consistência criptográfica é válida, mas a chave foi obtida do próprio pacote.",
          ),
    );

    return {
      result:
        manifest.status === "complete" ? "integral" : "integral_but_incomplete",
      sessionId: manifest.session_id,
      packageHash,
      membersVerified: packageIndex.members.length,
      temporalProof,
      attestationsVerified,
      trustMode,
      checks,
    };
  } finally {
    await archive.close();
  }
}

async function openArchive(blob: Blob): Promise<Archive> {
  const reader = new ZipReader(new BlobReader(blob), {
    checkAmbiguity: true,
    strictness: "strict",
  });
  let rawEntries;
  try {
    rawEntries = await reader.getEntries();
  } catch (error) {
    await reader.close();
    throw validationError("Não foi possível abrir o ZIP.", error);
  }
  ensure(rawEntries.length <= MAX_ENTRIES, "O ZIP contém arquivos demais.");
  const entries = new Map<string, FileEntry>();
  let totalSize = 0;
  for (const entry of rawEntries) {
    ensure(!entry.directory, "O ZIP não pode conter diretórios explícitos.");
    ensure(
      safeRelativePath(entry.filename),
      `Caminho inseguro: ${entry.filename}`,
    );
    ensure(
      !isSymbolicLink(entry.unixMode),
      `Link simbólico recusado: ${entry.filename}`,
    );
    ensure(
      !entry.encrypted,
      `Arquivo criptografado recusado: ${entry.filename}`,
    );
    ensure(
      entry.uncompressedSize <= MAX_FILE_SIZE,
      `Arquivo excede o limite do navegador: ${entry.filename}`,
    );
    const ratio =
      entry.compressedSize === 0
        ? entry.uncompressedSize
        : entry.uncompressedSize / entry.compressedSize;
    ensure(
      ratio <= MAX_COMPRESSION_RATIO,
      `Taxa de expansão suspeita: ${entry.filename}`,
    );
    totalSize += entry.uncompressedSize;
    ensure(
      totalSize <= MAX_TOTAL_SIZE,
      "O ZIP excede o limite total do navegador.",
    );
    ensure(!entries.has(entry.filename), `Nome duplicado: ${entry.filename}`);
    entries.set(entry.filename, entry);
  }
  return {
    entries,
    async read(path: string): Promise<Uint8Array> {
      const entry = entries.get(path);
      ensure(entry !== undefined, `Arquivo obrigatório ausente: ${path}`);
      try {
        const writer = new BlobWriter();
        const result = await entry.getData(writer, {
          checkSignature: true,
          checkAmbiguity: true,
          checkOverlappingEntry: true,
        });
        const blob = result ?? (await writer.getData());
        return new Uint8Array(await blob.arrayBuffer());
      } catch (error) {
        throw validationError(`Falha ao ler ${path}.`, error);
      }
    },
    async close(): Promise<void> {
      await reader.close();
    },
  };
}

function validatePackageIndex(value: PackageIndex): void {
  ensure(value.schema_version === "0.1.0", "Schema de índice não suportado.");
  ensure(nonEmpty(value.session_id), "O índice não identifica a sessão.");
  ensure(Array.isArray(value.members), "Lista de membros inválida.");
  const paths = new Set<string>();
  for (const member of value.members) {
    ensure(
      safeRelativePath(member.path),
      `Caminho indexado inseguro: ${member.path}`,
    );
    ensure(
      !paths.has(member.path),
      `Membro duplicado no índice: ${member.path}`,
    );
    paths.add(member.path);
    ensure(
      Number.isSafeInteger(member.size) && member.size >= 0,
      "Tamanho indexado inválido.",
    );
    ensure(nonEmpty(member.media_type), "Media type indexado vazio.");
    ensure(validSha256(member.sha256), "Hash indexado inválido.");
  }
}

function validatePublicKeys(value: PublicKeys): void {
  ensure(value.schema_version === "0.1.0", "Schema de chaves não suportado.");
  for (const key of [value.server, value.client]) {
    ensure(key.algorithm === "Ed25519", "Algoritmo de chave não suportado.");
    ensure(nonEmpty(key.key_id), "Key ID vazio.");
    ensure(
      /^[0-9a-f]{64}$/u.test(key.public_key_hex),
      "Chave Ed25519 inválida.",
    );
  }
}

function validateOperationalTrust(
  configured: string | undefined,
  packaged: Uint8Array,
): VerificationReport["trustMode"] {
  if (!configured?.trim()) return "self_declared";
  let trusted: Uint8Array;
  try {
    trusted = hexToBytes(configured.trim());
  } catch (error) {
    throw validationError(
      "A chave pública confiável não é hexadecimal válida.",
      error,
    );
  }
  ensure(trusted.length === 32, "A chave pública confiável deve ter 32 bytes.");
  ensure(
    bytesToHex(trusted) === bytesToHex(packaged),
    "A chave do pacote difere da chave confiável informada.",
  );
  return "custom_operational_key";
}

async function verifyIndexedMembers(
  archive: Archive,
  members: PackageMember[],
  excluded: Set<string>,
): Promise<void> {
  const expected = new Set(members.map((member) => member.path));
  const actual = new Set(
    [...archive.entries.keys()].filter((path) => !excluded.has(path)),
  );
  ensure(
    sameSet(actual, expected),
    "Os membros do ZIP diferem do índice assinado.",
  );
  for (const member of members) {
    const content = await archive.read(member.path);
    ensure(
      content.byteLength === member.size,
      `Tamanho divergente: ${member.path}`,
    );
    ensure(
      sha256Identifier(content) === member.sha256,
      `Hash divergente: ${member.path}`,
    );
  }
}

function validateManifest(
  manifest: CaptureManifest,
  index: PackageIndex,
): void {
  ensure(
    manifest.schema_version === "0.1.0",
    "Schema de manifesto não suportado.",
  );
  ensure(
    manifest.session_id === index.session_id,
    "Sessões do manifesto e índice divergem.",
  );
  ensure(
    ["complete", "incomplete"].includes(manifest.status),
    "Estado de captura inválido.",
  );
  ensure(
    Array.isArray(manifest.artifacts),
    "Artefatos do manifesto inválidos.",
  );
  ensure(
    Number.isSafeInteger(manifest.chain.entry_count),
    "Contagem de eventos inválida.",
  );
}

async function verifyArtifacts(
  archive: Archive,
  manifest: CaptureManifest,
): Promise<void> {
  for (const artifact of manifest.artifacts) {
    ensure(
      safeRelativePath(artifact.path),
      `Caminho de artefato inseguro: ${artifact.path}`,
    );
    if (artifact.status !== "captured") {
      ensure(
        artifact.artifact_hash === undefined,
        "Artefato ausente não pode declarar hash.",
      );
      continue;
    }
    const content = await archive.read(artifact.path);
    ensure(
      content.byteLength === artifact.size,
      `Tamanho de artefato divergente: ${artifact.path}`,
    );
    ensure(
      artifact.artifact_hash === sha256Identifier(content),
      `Hash de artefato divergente: ${artifact.path}`,
    );
  }
}

async function verifyEntryChain(
  archive: Archive,
  manifest: CaptureManifest,
  clientKey: Uint8Array,
): Promise<Map<number, string>> {
  const records = await readJsonLines<ChainRecord>(archive, ENTRIES_PATH);
  ensure(
    records.length === manifest.chain.entry_count,
    "Contagem da cadeia diverge do manifesto.",
  );
  ensure(records.length > 0, "A cadeia de eventos está vazia.");
  const entries = new Map<number, string>();
  let previous: string | null = null;
  for (const [index, record] of records.entries()) {
    const sequence = integerField(record.entry, "sequence");
    ensure(sequence === index, `Lacuna na sequência ${index}.`);
    ensure(
      stringField(record.entry, "session_id") === manifest.session_id,
      `Sessão divergente na sequência ${index}.`,
    );
    ensure(
      record.entry.previous_entry_hash === previous,
      `Hash anterior divergente na sequência ${index}.`,
    );
    const entryHash = sha256Identifier(canonicalBytes(record.entry));
    ensure(
      record.entry_hash === entryHash,
      `Hash divergente na sequência ${index}.`,
    );
    ensure(
      await verifyCanonical(
        DOMAINS.entry,
        record.entry,
        decodeHex(record.signature_hex, 64, "assinatura de entrada"),
        clientKey,
      ),
      `Assinatura inválida na sequência ${index}.`,
    );
    entries.set(sequence, entryHash);
    previous = entryHash;
  }
  const first = records[0];
  const last = records.at(-1);
  ensure(
    first !== undefined && last !== undefined,
    "A cadeia de eventos está vazia.",
  );
  ensure(
    manifest.chain.first_hash === first.entry_hash &&
      manifest.chain.last_hash === last.entry_hash &&
      manifest.chain.root_hash === last.entry_hash,
    "A raiz da cadeia diverge do manifesto.",
  );
  return entries;
}

async function verifyReceiptChain(
  archive: Archive,
  entries: Map<number, string>,
  serverKey: Uint8Array,
): Promise<number> {
  const records = await readJsonLines<ReceiptRecord>(archive, RECEIPTS_PATH);
  let previous: string | null = null;
  for (const record of records) {
    const sequence = integerField(record.receipt, "sequence");
    ensure(
      entries.get(sequence) === stringField(record.receipt, "entry_hash"),
      `Recibo referencia entrada desconhecida na sequência ${sequence}.`,
    );
    ensure(
      record.receipt.previous_receipt_hash === previous,
      `Cadeia de recibos diverge na sequência ${sequence}.`,
    );
    const receiptHash = sha256Identifier(canonicalBytes(record.receipt));
    ensure(
      record.receipt_hash === receiptHash,
      `Hash de recibo divergente na sequência ${sequence}.`,
    );
    ensure(
      await verifyCanonical(
        DOMAINS.receipt,
        record.receipt,
        decodeHex(record.signature_hex, 64, "assinatura de recibo"),
        serverKey,
      ),
      `Assinatura de recibo inválida na sequência ${sequence}.`,
    );
    previous = receiptHash;
  }
  return records.length;
}

async function verifyCaptureClose(
  archive: Archive,
  manifest: CaptureManifest,
  publicKeys: PublicKeys,
  clientKey: Uint8Array,
): Promise<void> {
  const close = await readJson<Record<string, unknown>>(
    archive,
    manifest.capture_close.path,
  );
  ensure(
    close.protocol_version === "0.1.0",
    "Protocolo de encerramento não suportado.",
  );
  ensure(
    close.session_id === manifest.session_id,
    "Sessão do encerramento diverge.",
  );
  ensure(
    close.session_root === manifest.chain.root_hash &&
      close.last_entry_hash === manifest.chain.last_hash &&
      close.entry_count === manifest.chain.entry_count,
    "Encerramento não corresponde à cadeia do manifesto.",
  );
  ensure(
    close.client_key_id === publicKeys.client.key_id,
    "Key ID do cliente diverge.",
  );
  ensure(
    close.client_public_key === base64Url(clientKey),
    "Chave pública do encerramento diverge.",
  );
  ensure(
    bytesToHex(canonicalBytes(close.artifacts)) ===
      bytesToHex(canonicalBytes(manifest.artifacts.map(closeArtifact))),
    "Artefatos do encerramento divergem do manifesto.",
  );
  const signature = await readHex(
    archive,
    manifest.capture_close.client_signature_path,
    64,
  );
  ensure(
    await verifyCanonical(DOMAINS.captureClose, close, signature, clientKey),
    "A assinatura de encerramento é inválida.",
  );
}

async function verifyProofBundle(
  file: File,
  manifest: CaptureManifest,
  serverKey: Uint8Array,
): Promise<{
  temporalProof: VerificationReport["temporalProof"];
  attestationsVerified: number;
  checks: VerificationCheck[];
}> {
  const archive = await openArchive(file);
  try {
    const index = await readJson<PackageIndex & { manifest_hash: string }>(
      archive,
      PROOF_INDEX_PATH,
    );
    ensure(
      index.schema_version === "0.1.0",
      "Schema do complemento não suportado.",
    );
    ensure(
      index.session_id === manifest.session_id,
      "Complemento pertence a outra sessão.",
    );
    const expectedManifestHash = sha256Identifier(canonicalBytes(manifest));
    ensure(
      index.manifest_hash === expectedManifestHash,
      "Complemento referencia outro manifesto.",
    );
    const signature = await readHex(archive, PROOF_INDEX_SIGNATURE_PATH, 64);
    ensure(
      await verifyCanonical(
        DOMAINS.proofBundleIndex,
        index,
        signature,
        serverKey,
      ),
      "A assinatura do complemento é inválida.",
    );
    await verifyIndexedMembers(
      archive,
      index.members,
      new Set([PROOF_INDEX_PATH, PROOF_INDEX_SIGNATURE_PATH]),
    );
    const attestations = await readJsonLines<{
      document: Record<string, unknown>;
      document_hash: string;
      signature_hex: string;
    }>(archive, ATTESTATIONS_PATH);
    ensure(attestations.length > 0, "O complemento não contém attestations.");
    let previous: string | null = null;
    let temporalProof: VerificationReport["temporalProof"] = "pending";
    for (const record of attestations) {
      ensure(
        record.document.manifest_hash === expectedManifestHash,
        "Attestation referencia outro manifesto.",
      );
      ensure(
        (record.document.previous_attestation_hash ?? null) === previous,
        "A cadeia de attestations está quebrada.",
      );
      const documentHash = sha256Identifier(canonicalBytes(record.document));
      ensure(
        record.document_hash === documentHash,
        "Hash de attestation divergente.",
      );
      ensure(
        await verifyCanonical(
          DOMAINS.attestation,
          record.document,
          decodeHex(record.signature_hex, 64, "assinatura de attestation"),
          serverKey,
        ),
        "Assinatura de attestation inválida.",
      );
      previous = documentHash;
      const timestampStatus = record.document.timestamp_status;
      const blockchainStatus = record.document.blockchain_status;
      if (timestampStatus === "valid" || blockchainStatus === "confirmed") {
        temporalProof = "signed_claims_only";
      }
    }
    return {
      temporalProof,
      attestationsVerified: attestations.length,
      checks: [
        valid(
          "proof_bundle",
          "Complemento probatório",
          `${attestations.length} attestations e todos os membros estão íntegros e assinados.`,
        ),
        warning(
          "external_proof_cryptography",
          "Criptografia temporal externa",
          "Esta versão web valida o vínculo e as assinaturas; a validação criptográfica completa de RFC 3161 e OpenTimestamps ainda requer a CLI.",
        ),
      ],
    };
  } finally {
    await archive.close();
  }
}

async function readJson<T>(archive: Archive, path: string): Promise<T> {
  const content = await archive.read(path);
  ensure(
    content.byteLength <= MAX_METADATA_SIZE,
    `JSON grande demais: ${path}`,
  );
  try {
    const value: unknown = JSON.parse(decoder.decode(content));
    validateJsonComplexity(value);
    return value as T;
  } catch (error) {
    throw validationError(`JSON inválido: ${path}`, error);
  }
}

async function readJsonLines<T>(archive: Archive, path: string): Promise<T[]> {
  const content = await archive.read(path);
  ensure(
    content.byteLength <= MAX_METADATA_SIZE,
    `JSONL grande demais: ${path}`,
  );
  try {
    return decoder
      .decode(content)
      .split("\n")
      .filter((line) => line.length > 0)
      .map((line) => {
        const value: unknown = JSON.parse(line);
        validateJsonComplexity(value);
        return value as T;
      });
  } catch (error) {
    throw validationError(`JSONL inválido: ${path}`, error);
  }
}

async function readHex(
  archive: Archive,
  path: string,
  length: number,
): Promise<Uint8Array> {
  const value = decoder.decode(await archive.read(path)).trim();
  return decodeHex(value, length, path);
}

function decodeHex(value: string, length: number, label: string): Uint8Array {
  let decoded;
  try {
    decoded = hexToBytes(value);
  } catch (error) {
    throw validationError(`${label} não contém hexadecimal válido.`, error);
  }
  ensure(decoded.length === length, `${label} possui tamanho inválido.`);
  return decoded;
}

async function hashFile(file: File): Promise<string> {
  const digest = sha256.create();
  const reader = file.stream().getReader();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    digest.update(value);
  }
  return `sha256:${bytesToHex(digest.digest())}`;
}

function closeArtifact(artifact: ManifestArtifact): Record<string, unknown> {
  const result: Record<string, unknown> = {
    artifact_id: artifact.artifact_id,
    path: artifact.path,
    size: artifact.size,
    status: artifact.status,
  };
  if (artifact.artifact_hash !== undefined) {
    result.artifact_hash = artifact.artifact_hash;
  }
  if (artifact.reason !== undefined) result.reason = artifact.reason;
  return result;
}

function validateJsonComplexity(value: unknown): void {
  const pending: Array<{ value: unknown; depth: number }> = [
    { value, depth: 0 },
  ];
  let nodes = 0;
  while (pending.length > 0) {
    const current = pending.pop();
    if (!current) break;
    ensure(
      current.depth <= MAX_JSON_DEPTH,
      "JSON excede a profundidade permitida.",
    );
    nodes += 1;
    ensure(nodes <= 1_000_000, "JSON contém elementos demais.");
    if (Array.isArray(current.value)) {
      for (const item of current.value) {
        pending.push({ value: item, depth: current.depth + 1 });
      }
    } else if (isObject(current.value)) {
      for (const item of Object.values(current.value)) {
        pending.push({ value: item, depth: current.depth + 1 });
      }
    }
  }
}

function safeRelativePath(path: string): boolean {
  if (
    path.length === 0 ||
    path.startsWith("/") ||
    path.includes("\\") ||
    path.includes("\0")
  ) {
    return false;
  }
  const parts = path.split("/");
  return parts.every(
    (part) => part.length > 0 && part !== "." && part !== "..",
  );
}

function isSymbolicLink(unixMode: number | undefined): boolean {
  return unixMode !== undefined && (unixMode & 0o170000) === 0o120000;
}

function validSha256(value: string): boolean {
  return /^sha256:[0-9a-f]{64}$/u.test(value);
}

function nonEmpty(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringField(value: Record<string, unknown>, field: string): string {
  const result = value[field];
  ensure(typeof result === "string", `Campo ${field} inválido.`);
  return result;
}

function integerField(value: Record<string, unknown>, field: string): number {
  const result = value[field];
  ensure(Number.isSafeInteger(result), `Campo ${field} inválido.`);
  return result as number;
}

function sameSet(left: Set<string>, right: Set<string>): boolean {
  return (
    left.size === right.size && [...left].every((value) => right.has(value))
  );
}

function base64Url(value: Uint8Array): string {
  return bytesToBase64(value)
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replace(/=+$/u, "");
}

function bytesToBase64(value: Uint8Array): string {
  let binary = "";
  for (const byte of value) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function valid(id: string, label: string, detail: string): VerificationCheck {
  return { id, label, status: "valid", detail };
}

function warning(id: string, label: string, detail: string): VerificationCheck {
  return { id, label, status: "warning", detail };
}

function ensure(condition: unknown, message: string): asserts condition {
  if (!condition) throw new EvidenceValidationError(message);
}

function validationError(
  message: string,
  cause: unknown,
): EvidenceValidationError {
  if (cause instanceof EvidenceValidationError) return cause;
  const detail = cause instanceof Error ? ` ${cause.message}` : "";
  return new EvidenceValidationError(`${message}${detail}`);
}
