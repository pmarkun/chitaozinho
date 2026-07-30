# Protocol schemas

Normative JSON Schemas for protocol and schema version `0.1.0`.

Changes that alter canonical bytes, required fields, hashes or signatures
require a new version and updated cross-language test vectors.

Additive optional fields may remain within a schema version only when they do
not change signed objects. Required fields, semantics, algorithms and canonical
representations require a new protocol or schema version. Implementations must
reject unknown major versions and may migrate only by creating a new artifact;
signed historical artifacts are never rewritten.
