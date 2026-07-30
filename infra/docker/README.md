# Local infrastructure

Local development runs PostgreSQL and Garage directly from `nix develop`; no
container runtime is required. See `scripts/local-services` and
`infra/local/garage.toml.in`.

Container definitions are reserved for OCI image validation and do not replace
the Nix development environment.
