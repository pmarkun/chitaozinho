# Dependency policy

- Lockfiles (`flake.lock`, `pnpm-lock.yaml`, `uv.lock`, `Cargo.lock`) are committed.
- Runtime dependencies require a concrete product or security need.
- Updates are reviewed with their changelog and security advisories.
- Protocol dependency updates must pass all cross-language vectors.
- Major updates are isolated in their own conventional commit.
- Dependencies with abandoned upstreams or known unpatched critical
  vulnerabilities are not permitted.
