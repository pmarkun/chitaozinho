# Verification

The Rust CLI verifies packages without authentication, backend or network
access.

```sh
cargo run -p chitaozinho-verifier -- verify \
  chitaozinho-evidence-session.zip \
  --trusted-server-key-hex <ed25519-public-key> \
  --html-report verification.html
```

The verifier:

- rejects unsafe paths, symlinks, duplicate names and suspicious expansion;
- imposes entry, file, total-size and metadata-memory limits;
- validates the signed package index and exact member set;
- recalculates package members and captured artifact hashes;
- validates manifest, entry, receipt and `capture_close` signatures;
- checks sequence, previous hashes, session root and receipt references;
- reports complete and incomplete captures separately.

Packaging copies source files into a temporary staging directory, validates
them, signs the manifest and package index, creates the ZIP, and writes a
detached `.sha256` file. It never changes the source directory.
