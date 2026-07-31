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

Issue an operational certificate for at most 90 days. Generate a fresh
operational seed on a trusted machine, keep it mode `0600`, and publish only its
public key. In staging and production, inject the seed through a runtime secret
mount (for example OpenBao Agent, SOPS or the platform secret store) and set
`CHITAOZINHO_SERVER_SEED_PATH`. Never place the seed in an environment variable,
image, repository or persistent application volume.

```sh
nix develop --command scripts/key-management generate-operational-file \
  --output-dir /secure/operations/server-2026-q3 \
  --operational-key-id server-2026-q3
```

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
