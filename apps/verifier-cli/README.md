# Chitãozinho verifier

The base evidence ZIP is verified locally without the backend:

```sh
chitaozinho-verify verify evidence.zip \
  --trusted-root-key-hex "$ROOT_PUBLIC_KEY_HEX" \
  --json --html-report report.html
```

External attestations are append-only and distributed in a separate signed
proof bundle so the original ZIP never changes:

```sh
chitaozinho-verify verify evidence.zip \
  --proof-bundle proofs.zip \
  --trusted-root-key-hex "$ROOT_PUBLIC_KEY_HEX"
```

`--trusted-root-key-hex` validates the operational key certificate and
cumulative signed revocation snapshot embedded in the package, including their
effect at package signing time, and reports `offline_root_delegation`.
Development fixtures may instead use `--trusted-server-key-hex`, which is
reported explicitly as `custom_operational_key`.

Use `--key-revocation-list latest-revocations.json` with root trust to check a
newer independently published snapshot instead of the one preserved in the
package. Its root signature and issuer are always verified.

For an RFC 3161 attestation marked valid, pass explicit CA and CRL bundles.
The verifier fails closed if either is absent. Confirmed OpenTimestamps proofs
are checked with the `ots` client; pending proofs are parsed and reported as
pending.

Reproducibility is checked by building the release binary twice in isolated
target directories:

```sh
nix develop --command ./scripts/check-verifier-reproducibility
```
