# Local infrastructure

Local development runs PostgreSQL and Garage directly from `nix develop`; no
container runtime is required. See `scripts/local-services` and
`infra/local/garage.toml.in`.

Container definitions are reserved for OCI image validation and do not replace
the Nix development environment.

## Production image

`Dockerfile` builds one non-root image for both processes:

- API: the image default command, or the command in `.railway/railway.ts`;
- timestamp worker and retention cron: their commands in `.railway/railway.ts`.

Both base images are pinned by multi-platform digest. Third-party Python
dependencies come only from `uv.lock`; application sources are copied directly
and the runtime contains no development tools. Run
`scripts/check-oci-reproducibility` to build the `linux/amd64` image twice with
normalized timestamps and compare the resulting manifest digests.

`.railway/railway.ts` is the declarative staging topology. Preview it with
`railway config plan` and apply it only after reviewing the change set.
`scripts/check-railway-config.py` rejects drift from the deployment contract:
the API alone runs migrations and gates traffic on `/readyz`; API, worker and
retention cron cannot mount evidence volumes; and only private OpenBao receives
a persistent volume. The Docker API command uses an explicit shell so
Railway's injected `$PORT` is expanded before Uvicorn starts.

The public verifier uses `Dockerfile.verifier-web`, serves the static build
through Caddy, checks `/health` and keeps validation local to the browser.
