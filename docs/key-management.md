# Key management

Production verification uses an offline Ed25519 root to certify short-lived
operational server keys. Generate the root only on an offline encrypted
machine:

```sh
nix develop --command scripts/key-management generate-root \
  --output-dir /secure/offline/chitaozinho-root \
  --key-id root-2026-01
```

`root.seed` is secret and must never enter this repository, logs, Railway or
online backups. Publish `root-public.json` through an independently controlled
channel.

Issue an operational certificate for at most 90 days:

First generate a fresh operational key directly into a KMS envelope. The
plaintext seed exists only in process memory and is never written:

```sh
nix develop --command scripts/key-management generate-operational-envelope \
  --output-dir /secure/operations/server-2026-q3 \
  --operational-key-id server-2026-q3 \
  --kms-key-arn "$SIGNING_ENVELOPE_KMS_KEY_ARN" \
  --region sa-east-1
```

The command binds the ciphertext to the application, purpose and operational
key ID through the KMS encryption context. Give the production runtime only
`kms:Decrypt` for this KMS key and exact context; keep `kms:Encrypt` with the
rotation operator. Configure the resulting Base64 file as
`CHITAOZINHO_SERVER_SEED_KMS_CIPHERTEXT_B64`, the ARN as
`CHITAOZINHO_SERVER_SEED_KMS_KEY_ID`, and never configure
`CHITAOZINHO_SERVER_SEED_HEX` outside local development.

Use the public key from the generated `.public.json` when issuing the
certificate:

```sh
nix develop --command scripts/key-management issue-operational \
  --root-seed-file /secure/offline/chitaozinho-root/root.seed \
  --root-key-id root-2026-01 \
  --operational-key-id server-2026-q3 \
  --operational-public-key-hex "$SERVER_PUBLIC_KEY_HEX" \
  --valid-from 2026-07-30T00:00:00Z \
  --valid-until 2026-10-28T00:00:00Z \
  --output server-2026-q3.certificate.json
```

For an existing operational seed, `encrypt-operational` imports it into the
same envelope format without modifying or deleting the source file:

```sh
nix develop --command scripts/key-management encrypt-operational \
  --seed-file /secure/legacy/server.seed \
  --kms-key-arn "$SIGNING_ENVELOPE_KMS_KEY_ARN" \
  --operational-key-id server-2026-q3 \
  --output server-2026-q3.seed.kms.b64
```

Maintain revocations as a monotonically sequenced, root-signed snapshot. The
input is a JSON array and must retain every previous revocation:

```json
[
  {
    "key_id": "server-2026-q2",
    "revoked_at": "2026-07-30T18:00:00Z",
    "reason": "scheduled rotation"
  }
]
```

```sh
nix develop --command scripts/key-management issue-revocations \
  --root-seed-file /secure/offline/chitaozinho-root/root.seed \
  --root-key-id root-2026-01 \
  --sequence 1 \
  --issued-at 2026-07-30T18:00:00Z \
  --revocations-file revocations.json \
  --output key-revocations-1.json
```

Never overwrite a published list; publish the new sequence beside the old one.
Staging and production refuse startup without a matching certificate and a
signed revocation snapshot. Every package preserves both. The verifier checks
the root signatures, certificate validity and revocation time at package
signing. Direct operational-key trust remains available only as an explicit
development mode.

In Railway, configure the public documents directly as
`CHITAOZINHO_SERVER_CERTIFICATE_JSON`,
`CHITAOZINHO_SERVER_REVOCATION_LIST_JSON` and
`CHITAOZINHO_SERVER_ROOT_PUBLIC_JSON`. File-based deployments may use the
corresponding `_PATH` variables. Configure exactly one source for each
document; startup fails on missing, ambiguous or invalid JSON.
