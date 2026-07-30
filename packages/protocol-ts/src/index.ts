import { sha256 } from "@noble/hashes/sha2.js";
import { canonicalize } from "json-canonicalize";

const encoder = new TextEncoder();
const PKCS8_ED25519_PREFIX = hexToBytes("302e020100300506032b657004220420");
const SPKI_ED25519_PREFIX = hexToBytes("302a300506032b6570032100");

export const DOMAINS = {
  entry: "CHITAOZINHO/ENTRY/v1",
  receipt: "CHITAOZINHO/RECEIPT/v1",
  captureClose: "CHITAOZINHO/CAPTURE_CLOSE/v1",
  manifest: "CHITAOZINHO/MANIFEST/v1",
  packageIndex: "CHITAOZINHO/PACKAGE_INDEX/v1",
  attestation: "CHITAOZINHO/ATTESTATION/v1",
} as const;

export function canonicalBytes(value: unknown): Uint8Array {
  const result = canonicalize(value);
  if (result === undefined) {
    throw new TypeError("value cannot be represented as canonical JSON");
  }
  return encoder.encode(result);
}

export function sha256Bytes(data: Uint8Array): Uint8Array {
  return sha256(data);
}

export function sha256Identifier(data: Uint8Array): string {
  return `sha256:${bytesToHex(sha256Bytes(data))}`;
}

export function base64UrlEncode(data: Uint8Array): string {
  let binary = "";
  for (const byte of data) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary)
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replace(/=+$/, "");
}

export function base64UrlDecode(value: string): Uint8Array {
  if (!/^[A-Za-z0-9_-]*$/.test(value)) {
    throw new TypeError("invalid Base64URL without padding");
  }
  const padding = "=".repeat((4 - (value.length % 4)) % 4);
  const binary = atob(
    value.replaceAll("-", "+").replaceAll("_", "/") + padding,
  );
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

export function hashCanonical(value: unknown): Uint8Array {
  return sha256Bytes(canonicalBytes(value));
}

export async function signCanonical(
  domain: string,
  value: unknown,
  privateSeed: Uint8Array,
): Promise<Uint8Array> {
  if (privateSeed.length !== 32) {
    throw new RangeError("Ed25519 private seed must contain 32 bytes");
  }
  const keyData = concatBytes(PKCS8_ED25519_PREFIX, privateSeed);
  const key = await crypto.subtle.importKey(
    "pkcs8",
    asArrayBuffer(keyData),
    { name: "Ed25519" },
    false,
    ["sign"],
  );
  const message = concatBytes(encoder.encode(domain), hashCanonical(value));
  return new Uint8Array(
    await crypto.subtle.sign("Ed25519", key, asArrayBuffer(message)),
  );
}

export async function signCanonicalWithKey(
  domain: string,
  value: unknown,
  privateKey: CryptoKey,
): Promise<Uint8Array> {
  const message = concatBytes(encoder.encode(domain), hashCanonical(value));
  return new Uint8Array(
    await crypto.subtle.sign("Ed25519", privateKey, asArrayBuffer(message)),
  );
}

export async function verifyCanonical(
  domain: string,
  value: unknown,
  signature: Uint8Array,
  publicKey: Uint8Array,
): Promise<boolean> {
  if (publicKey.length !== 32) {
    throw new RangeError("Ed25519 public key must contain 32 bytes");
  }
  const keyData = concatBytes(SPKI_ED25519_PREFIX, publicKey);
  const key = await crypto.subtle.importKey(
    "spki",
    asArrayBuffer(keyData),
    { name: "Ed25519" },
    false,
    ["verify"],
  );
  const message = concatBytes(encoder.encode(domain), hashCanonical(value));
  return crypto.subtle.verify(
    "Ed25519",
    key,
    asArrayBuffer(signature),
    asArrayBuffer(message),
  );
}

export function hexToBytes(value: string): Uint8Array {
  if (value.length % 2 !== 0 || !/^[0-9a-f]*$/i.test(value)) {
    throw new TypeError("invalid hexadecimal string");
  }
  return Uint8Array.from(value.match(/.{2}/g) ?? [], (byte) =>
    Number.parseInt(byte, 16),
  );
}

export function bytesToHex(value: Uint8Array): string {
  return Array.from(value, (byte) => byte.toString(16).padStart(2, "0")).join(
    "",
  );
}

function concatBytes(...values: Uint8Array[]): Uint8Array {
  const result = new Uint8Array(
    values.reduce((size, value) => size + value.length, 0),
  );
  let offset = 0;
  for (const value of values) {
    result.set(value, offset);
    offset += value.length;
  }
  return result;
}

function asArrayBuffer(value: Uint8Array): ArrayBuffer {
  const result = new ArrayBuffer(value.byteLength);
  new Uint8Array(result).set(value);
  return result;
}
