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

`--trusted-root-key-hex` validates the operational key certificate embedded in
the package and reports `offline_root_delegation`. Development fixtures may
instead use `--trusted-server-key-hex`, which is reported explicitly as
`custom_operational_key`.

For an RFC 3161 attestation marked valid, pass explicit CA and CRL bundles.
The verifier fails closed if either is absent. Confirmed OpenTimestamps proofs
are checked with the `ots` client; pending proofs are parsed and reported as
pending.
