# Security review

Every CI run scans the tracked source tree only:

- OSV Scanner checks locked Rust, Python and npm dependencies, with Rust call
  analysis;
- Trivy checks Terraform, Docker and workflow configuration for high/critical
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
provider IAM, TLS, KMS/HSM and Object Lock configuration.
