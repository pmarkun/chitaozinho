export const VIDEO_BITS_PER_SECOND = 2_000_000;

const WEBM_CANDIDATES = [
  "video/webm;codecs=vp8,opus",
  "video/webm;codecs=vp9,opus",
  "video/webm",
] as const;

export function preferredRecordingMimeType(
  isTypeSupported: (mimeType: string) => boolean,
): string {
  return WEBM_CANDIDATES.find(isTypeSupported) ?? "";
}
