# Smoke tests

## 2026-07-30 — Chromium unpacked

- Session: `b2c9473425e04893bf25ddc7cc50e336`
- Capture duration: `6,871 ms`
- Package SHA-256:
  `dc1af5433a1a7fb334755e3a98032a04f94148be93ced59ac83042676b30039c`
- Source: public web page; captured content is not stored in this repository.
- Artifacts: DOM, client-reported metadata, WebM recording and two viewport
  screenshots.
- Chain: 13 entries, two incremental video parts, no known gaps.
- Offline verifier: `integral`, 12 members verified, artifact/index/manifest
  hashes and signatures, entry/receipt chains and `capture_close` valid.
- Temporal proof: `not_provided`, as expected for the functional POC smoke.
- Media probe: VP9 video at 1920×1080 and Opus audio; final video timestamp
  approximately `6.496 s`. FFmpeg decoded the file with exit code zero and
  reported one malformed Opus packet warning.
- External checksum matched the ZIP. The smoke exposed that the sidecar used a
  protocol-prefixed digest; subsequent sidecars use standard `sha256sum`
  syntax.

This run proves the short functional flow. It does not satisfy the separate
60-second capture gate.
