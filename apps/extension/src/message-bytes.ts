import { base64UrlDecode, base64UrlEncode } from "@chitaozinho/protocol";

export function encodeMessageBytes(bytes: ArrayBuffer): string {
  return base64UrlEncode(new Uint8Array(bytes));
}

export function decodeMessageBytes(value: string): ArrayBuffer {
  const decoded = base64UrlDecode(value);
  return decoded.buffer.slice(
    decoded.byteOffset,
    decoded.byteOffset + decoded.byteLength,
  ) as ArrayBuffer;
}
