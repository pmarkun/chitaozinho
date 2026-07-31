import { base64UrlEncode, canonicalBytes } from "@chitaozinho/protocol";

import type { ChainEntry } from "./types";

const API_BASE_URL = __CHITAOZINHO_ENDPOINTS__.api;

function apiFetch(input: RequestInfo | URL, init?: RequestInit) {
  return fetch(input, { ...init, credentials: "include" });
}

interface SignedEntry {
  entry: ChainEntry;
  entry_hash: string;
  signature_hex: string;
}

async function checked(response: Response): Promise<Response> {
  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
  return response;
}

export async function createSession(): Promise<Record<string, unknown>> {
  return (
    await checked(
      await apiFetch(`${API_BASE_URL}/v1/sessions`, { method: "POST" }),
    )
  ).json();
}

export async function registerKey(
  sessionId: string,
  keyId: string,
  publicKey: Uint8Array,
): Promise<void> {
  await checked(
    await apiFetch(`${API_BASE_URL}/v1/sessions/${sessionId}/keys`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        key_id: keyId,
        public_key: base64UrlEncode(publicKey),
      }),
    }),
  );
}

export async function sendEvent(
  sessionId: string,
  signed: SignedEntry,
  idempotencyKey: string,
): Promise<void> {
  await checked(
    await apiFetch(`${API_BASE_URL}/v1/sessions/${sessionId}/events`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(signed),
    }),
  );
}

export async function uploadPart(
  sessionId: string,
  artifactId: string,
  partNumber: number,
  bytes: ArrayBuffer,
  signed: SignedEntry,
): Promise<Record<string, unknown>> {
  return (
    await checked(
      await apiFetch(
        `${API_BASE_URL}/v1/sessions/${sessionId}/artifacts/${artifactId}/parts/${partNumber}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/octet-stream",
            "Idempotency-Key": `${artifactId}-${partNumber}`,
            "X-Entry-Json": base64UrlEncode(canonicalBytes(signed.entry)),
            "X-Entry-Hash": signed.entry_hash,
            "X-Entry-Signature": signed.signature_hex,
          },
          body: bytes,
        },
      ),
    )
  ).json();
}

export async function completeArtifact(
  sessionId: string,
  artifactId: string,
  body: Record<string, unknown>,
): Promise<void> {
  await checked(
    await apiFetch(
      `${API_BASE_URL}/v1/sessions/${sessionId}/artifacts/${artifactId}/complete`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    ),
  );
}

export async function declareArtifactUnavailable(
  sessionId: string,
  artifactId: string,
  body: Record<string, unknown>,
): Promise<void> {
  await checked(
    await apiFetch(
      `${API_BASE_URL}/v1/sessions/${sessionId}/artifacts/${artifactId}/unavailable`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    ),
  );
}

export async function finalizeSession(
  sessionId: string,
  captureClose: Record<string, unknown>,
  signatureHex: string,
): Promise<Record<string, unknown>> {
  return (
    await checked(
      await apiFetch(`${API_BASE_URL}/v1/sessions/${sessionId}/finalize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          capture_close: captureClose,
          signature_hex: signatureHex,
        }),
      }),
    )
  ).json();
}

interface DownloadUrls {
  packageUrl: string;
  checksumUrl: string;
  expiresAt: string;
}

export async function createDownloadUrls(
  sessionId: string,
): Promise<DownloadUrls> {
  const response = await checked(
    await apiFetch(`${API_BASE_URL}/v1/sessions/${sessionId}/download-urls`, {
      method: "POST",
    }),
  );
  const body = (await response.json()) as Record<string, unknown>;
  return {
    packageUrl: String(body.package_url),
    checksumUrl: String(body.checksum_url),
    expiresAt: String(body.expires_at),
  };
}

export async function preparePackage(sessionId: string): Promise<{
  packageHash: string;
  storageStatus: string;
  packageUrl: string;
  checksumUrl: string;
}> {
  const urls = await createDownloadUrls(sessionId);
  const response = await checked(await apiFetch(urls.checksumUrl));
  const digest = (await response.text()).trim().split(/\s+/, 1)[0];
  return {
    packageHash: digest.startsWith("sha256:") ? digest : `sha256:${digest}`,
    storageStatus: response.headers.get("X-Storage-Status") ?? "unknown",
    packageUrl: urls.packageUrl,
    checksumUrl: urls.checksumUrl,
  };
}

export async function authStatus(): Promise<boolean> {
  const response = await checked(
    await apiFetch(`${API_BASE_URL}/v1/auth/session`),
  );
  return Boolean((await response.json()).authenticated);
}

export async function requestMagicLink(email: string): Promise<void> {
  await checked(
    await apiFetch(`${API_BASE_URL}/v1/auth/magic-links`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    }),
  );
}
