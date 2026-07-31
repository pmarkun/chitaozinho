# Security review

Every CI run scans the tracked source tree only:

- OSV Scanner checks locked Rust, Python and npm dependencies, with Rust call
  analysis;
- Trivy checks Ceph, Docker and workflow configuration for high/critical
  misconfigurations and scans committed files for secrets.

The gate has one exact OSV exception:
`GHSA-mh99-v99m-4gvg` for the development-only transitive dependency
`brace-expansion@1.1.18`. The upstream advisory lists `1.1.17` as the patched
1.x release, while the aggregated OSV range currently reports every version
through `5.0.7` as affected. The exception is bound to the advisory, package and
version; any change is rejected and must be reviewed again.

Run the same gate locally with:

```sh
nix develop --command ./scripts/security-audit
```

This automated gate complements the threat model, negative protocol vectors,
authentication/owner-isolation tests and hostile-package tests. It does not
replace an independent human review of the deployed staging environment,
RGW access, TLS, OpenBao policies and Object Lock configuration.

## 2026-07-30 POC code review

Scope reviewed:

- magic-link and access-token lifecycle, cookie flags, CORS, CSRF origin checks,
  owner isolation and bounded download tokens;
- client/server signatures, root-signed operational keys, revocation handling,
  audit-chain immutability and deterministic protocol serialization;
- upload idempotency, local and S3 storage boundaries, final-object retention
  verification and package generation;
- hostile ZIP handling, resource limits, external command invocation, structured
  logging and secret redaction;
- public-environment, Railway, Ceph, monitoring, backup and recovery gates.

Two defense-in-depth findings were fixed during the review:

- local storage reads now reject absolute paths, parent traversal and symlink
  escapes, including when a persisted storage key is tampered with
  (`e99eb11`);
- local and S3 part reads now enforce the configured part-size ceiling and
  reject inconsistent S3 length metadata before packaging (`7aeeea9`).

The deployment probe now proves both halves of the modern-TLS requirement:
TLS 1.2 or 1.3 must negotiate, while TLS 1.0 and 1.1 must fail (`8b6d9bd`).

The POC controls cover post-capture alteration, substitution, reordering,
removal, interruption, false completeness and untrusted verifier builds.
Object deletion and administrator/backend compromise remain only partially
mitigated until the isolated Ceph Object Lock test passes. Browser, operating
system, account and pre-capture compromise remain explicitly outside the
platform's proof boundary, as required by the threat model.

The code-level review is complete with no known unresolved high or critical
finding. The production security-review gate remains open until staging exists
and an independent reviewer checks RGW capabilities, live TLS, secret
management, Object Lock, monitoring and the deployed image identity.
