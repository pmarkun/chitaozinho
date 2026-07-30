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

## 2026-07-30 — Chromium unpacked, 60-second gate

- Session: `5231c8c9394049b1b9c7d99520b23fd7`
- Capture duration: `70,552 ms` by the signed client events.
- Recording interval: `65,660 ms` in the signed artifact context; the last
  media packet timestamp is approximately `69.693 s`.
- Package SHA-256:
  `ddf1f4384dd411959d9f7073b8e0d19449f2b8751904ae92ae0c36295ce59e0b`
- The standard `sha256sum` sidecar matched the ZIP.
- Source: public page at `https://www.wikiaves.com.br/`; captured content is
  not stored in this repository.
- Artifacts: DOM, client-reported metadata, VP9/Opus WebM recording and three
  viewport screenshots, all marked captured with no known gaps.
- Artifact completion events record method, client-reported provenance,
  permissions, covered interval and completeness for all six artifacts.
- Chain: 49 entries — 22 artifact parts, six completions, 16 scroll events,
  two navigations, one marker, start and finish. Scroll positions cover
  `y=480` through `y=10087`.
- Offline verifier: `integral`, 13 members verified, artifact/index/manifest
  hashes and signatures, entry/receipt chains and `capture_close` valid.
- Verification report SHA-256:
  `aa6db20ce48813009fc389e72ccef965cb0c32660f6f96fe298d4290133bffd2`.
- Temporal proof: `not_provided`, as expected for this functional POC smoke.
- Media probe: 676 VP9 packets through `69.583 s` and 1,162 Opus packets
  through `69.693 s`; DTS is strictly increasing inside each stream. FFmpeg
  decoded with exit code zero, but reported timestamp rounding warnings at the
  null muxer and one malformed Opus packet header.
- Build identity: version `0.1.0`, source commit
  `0186c7be62669dd8e20890c61ea200e96a129201-dirty`. The functional gate is
  accepted, but a subsequent reproducibility or release smoke must use a clean
  build identity.

## Automated recovery checks

- Finalization rejects a session when persisted artifact parts have no
  immutable artifact result. The client must complete the artifact or declare
  it unavailable or failed, so missing parts cannot be silently omitted from
  `capture_close`.
- A simulated network failure leaves the recording part, chain position and
  upload count unchanged in IndexedDB. Retrying with the same signed entry
  stores one receipt, advances the upload count once and makes subsequent
  retries no-ops.
- A simulated process exit after committing finalization but before returning
  the HTTP response is recovered by a fresh API instance. Replaying the same
  signed `capture_close` returns the persisted final result.
- A capture declaring client wall-clock values in 2001 remains valid, while
  the separately recorded server start/end times stay anchored to the actual
  request time. The client clock is preserved as a declaration, not trusted as
  temporal proof.

## 2026-07-30 — Release supply chain

- The local release harness generated the verifier, extension ZIP and OCI API
  archive plus artifact and source SPDX 2.3 SBOMs.
- The source SBOM catalogued 833 package/manifests across the locked Rust,
  Python, npm, Terraform and workflow dependency graph.
- Every entry in `SHA256SUMS` verified. Its SHA-256 was
  `d38ecee8cc7b2993e1be400a40eae25c403d7fb1cbef91df65cdbed0769c2db2`.
- An ephemeral local Cosign key signed the checksum file into a Sigstore bundle
  and `cosign verify-blob` returned `Verified OK`. Tagged releases use GitHub
  OIDC instead of a stored signing key.

## 2026-07-30 — PostgreSQL backup and restore

- A fully migrated synthetic PostgreSQL source was dumped in custom format and
  restored into a separately named database.
- The restored public schema contained the same 17 tables and exact row counts.
- Running migrations against the restored copy was a no-op at
  `0005_magic_link_auth (head)`.
- Both temporary databases were removed after validation; the development
  database was not modified.
