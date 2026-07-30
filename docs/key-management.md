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

Staging and production refuse startup without a matching certificate. The
verifier checks its root signature and validity at the package signing time.
Direct operational-key trust remains available only as an explicit development
mode.
