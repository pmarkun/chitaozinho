# Evidence retention

Local development stores final artifacts durably and reports `stored`; it never
claims WORM retention. Outside local development, configuration requires S3.

For every generated evidence package and proof bundle, the API:

1. uploads to a content-addressed key with `If-None-Match: *`;
2. requests server-side encryption and Object Lock `COMPLIANCE`;
3. sets the retention deadline from the capture end plus the configured days;
4. reads the object back with `HeadObject`;
5. reports `locked` only when digest metadata, size, encryption, version ID,
   lock mode and retention deadline are all present and consistent.

Any exception or incomplete response records an append-only
`evidence_retention_evaluated` audit event with `retention_failed`. Error
messages, credentials and object contents are not recorded.

`CHITAOZINHO_RETENTION_DAYS` defaults to 90. Changing a live policy or testing
COMPLIANCE deletion requires an explicit, separate operational approval.
