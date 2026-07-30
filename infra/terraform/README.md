# Production infrastructure

Declarative resources for Railway integrations and external S3 live here.

The S3 module creates a bucket in `sa-east-1` with versioning, Object Lock and
a dedicated customer-managed KMS key with automatic rotation enabled at
creation, default `COMPLIANCE` retention, encryption at rest,
complete public-access blocking, TLS-only access and `prevent_destroy`.

```sh
nix develop --command tofu -chdir=infra/terraform init -backend=false
nix develop --command tofu -chdir=infra/terraform validate
```

Do not run `apply` casually. The isolated POC test uses only synthetic/public
content and `retention_days=1`. Production starts at 90 days and requires
legal/security approval.
