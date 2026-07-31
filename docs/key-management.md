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

Issue an operational certificate for at most 90 days. Development may use a
local seed, but staging and production require a non-exportable Ed25519 key in
OpenBao Transit. The application reads only the public key and sends the exact
domain-separated digest for signing; the private key never reaches Railway,
the application process, an environment variable or a mounted volume.

Create the Transit key and least-privilege runtime policy as described in
`infra/openbao/README.md`. Read the public key for the pinned key version and use
its raw 32-byte hex value when issuing the certificate:

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
