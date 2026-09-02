# Protocol schemas

Normative JSON Schemas for protocol version `0.1.0`. The latest schema version
is `0.1.1`; individual artifacts retain their declared version, and historical
signed artifacts are not rewritten.

Changes that alter canonical bytes, required fields, hashes or signatures
require a new version and updated cross-language test vectors.

`version.json` is the machine-readable version contract used by CI. A pull
request that changes a normative `*.schema.json` file must also bump the
applicable version there.

Additive optional fields may remain within a schema version only when they do
not change signed objects. Required fields, semantics, algorithms and canonical
representations require a new protocol or schema version. Implementations must
reject unknown major versions and may migrate only by creating a new artifact;
signed historical artifacts are never rewritten.
