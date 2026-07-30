# Evidence format

Normative schemas and test vectors are maintained under `packages/schemas/`
and `test-vectors/`.

Every signed object uses a distinct ASCII domain prefix. Operational key
certificates use `CHITAOZINHO/KEY_CERTIFICATE/v1`; cumulative key revocation
snapshots use `CHITAOZINHO/KEY_REVOCATION_LIST/v1`. They are separate signed
objects and are never embedded in another object's signature input.
