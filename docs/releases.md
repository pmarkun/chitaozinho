# Releases

A `vX.Y.Z` tag must match the shared Rust, Python and extension version. The
release workflow builds a Linux verifier, the unpacked-extension ZIP and an OCI
API archive from a clean checkout. It emits artifact SPDX JSON SBOMs, a source
dependency SBOM covering the Rust, Python, npm, Terraform and workflow
manifests, and SHA-256 checksums.

Every artifact, SBOM and checksum file receives a Sigstore bundle created by
`cosign sign-blob` with GitHub OIDC. Consumers can verify identity, repository
and workflow provenance with `cosign verify-blob` and the adjacent
`.sigstore.json` bundle. No long-lived signing key is stored in GitHub or
Railway.

Build locally into a new empty directory:

```sh
nix develop --command ./scripts/build-release-artifacts /tmp/chitaozinho-release
```

The workflow publishes only immutable tags. It does not deploy Railway
services; deployment remains a separately authorized operation.
