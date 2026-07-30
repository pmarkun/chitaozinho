# Chitãozinho verifier

The base evidence ZIP is verified locally without the backend:

```sh
chitaozinho-verify verify evidence.zip \
  --trusted-server-key-hex "$SERVER_PUBLIC_KEY_HEX" \
  --json --html-report report.html
```

External attestations are append-only and distributed in a separate signed
proof bundle so the original ZIP never changes:

```sh
chitaozinho-verify verify evidence.zip \
  --proof-bundle proofs.zip \
  --trusted-server-key-hex "$SERVER_PUBLIC_KEY_HEX"
```

For an RFC 3161 attestation marked valid, pass explicit CA and CRL bundles.
The verifier fails closed if either is absent. Confirmed OpenTimestamps proofs
are checked with the `ots` client; pending proofs are parsed and reported as
pending.
