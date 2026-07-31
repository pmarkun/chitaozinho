# Production infrastructure

Declarative resources for Railway integrations and external S3 live here.

The S3 module creates a bucket in `sa-east-1` with versioning, Object Lock and
a dedicated customer-managed KMS key with automatic rotation enabled at
creation, default `COMPLIANCE` retention, encryption at rest,
complete public-access blocking, TLS-only access and `prevent_destroy`.
The bucket policy also rejects uploads that do not explicitly request the
dedicated KMS key. The `runtime_iam_policy_json` output is the minimum policy
to attach to the credentials shared by the Railway API and worker.

```sh
nix develop --command tofu -chdir=infra/terraform init -backend=false
nix develop --command tofu -chdir=infra/terraform validate
nix develop --command tofu -chdir=infra/terraform test
```

Do not run `apply` casually. The isolated POC test uses only synthetic/public
content, `environment=test` and `retention_days=1`. Staging and production
reject retention below 90 days and require legal/security approval. The module
also rejects regions other than `sa-east-1`.

Set `CHITAOZINHO_S3_KMS_KEY_ID` to `evidence_kms_key_arn` and
`CHITAOZINHO_SERVER_SEED_KMS_KEY_ID` to `signing_envelope_kms_key_arn` in the
published API and worker environments. Non-local startup fails closed without
both values. Final-object verification checks the evidence key, while the
operational Ed25519 seed is decrypted with a purpose- and key-ID-bound KMS
encryption context.

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
