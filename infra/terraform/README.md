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

Set `CHITAOZINHO_S3_KMS_KEY_ID` to the `evidence_kms_key_arn` output in the
published API and worker environments. Non-local startup fails closed without
this value, and final-object verification checks that S3 reports the same key.

After explicit authorization, validate the isolated one-day test bucket with:

```sh
CHITAOZINHO_RUN_OBJECT_LOCK_TEST=I_ACCEPT_24H_RETENTION \
  nix develop --command uv run scripts/test-s3-object-lock \
  --output /tmp/chitaozinho-object-lock-report.json
```

The command uploads only embedded synthetic fixtures. It verifies bucket
versioning, one-day `COMPLIANCE` retention, the configured KMS key, version IDs,
conditional overwrite refusal and early version-delete refusal. The retained
objects cannot be cleaned up until their reported retention timestamps expire.
