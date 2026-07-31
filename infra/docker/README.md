# Local infrastructure

Local development runs PostgreSQL and Garage directly from `nix develop`; no
container runtime is required. See `scripts/local-services` and
`infra/local/garage.toml.in`.

Container definitions are reserved for OCI image validation and do not replace
the Nix development environment.

## Production image

`Dockerfile` builds one non-root image for both processes:

- API: the image default command, or the command in `infra/railway/api.json`;
- timestamp worker: the command in `infra/railway/worker.json`.

Both base images are pinned by multi-platform digest. Third-party Python
dependencies come only from `uv.lock`; application sources are copied directly
and the runtime contains no development tools. Run
`scripts/check-oci-reproducibility` to build the `linux/amd64` image twice with
normalized timestamps and compare the resulting manifest digests.

The Railway files are declarative templates. Configure each service to use its
corresponding config path. They do not authorize or perform a deployment.
`scripts/check-railway-config.py` rejects drift from the deployment contract:
the API alone runs migrations and gates traffic on `/readyz`, API and worker
remain separate processes with bounded restarts, and neither template can
declare a Railway volume for evidence. The Docker API command uses an explicit
shell so Railway's injected `$PORT` is expanded before Uvicorn starts.

The public verifier uses `Dockerfile.verifier-web` and
`infra/railway/verifier-web.json`. It serves the static build through Caddy,
checks `/health` and keeps validation local to the browser.
