# API

FastAPI service for capture sessions, durable receipts and package generation.

Unit tests use SQLite and filesystem storage. For the local integration profile,
start PostgreSQL and Garage from the repository root, then load its environment:

```sh
nix develop --command ./scripts/local-services start
set -a; source .env.local-services; set +a
CHITAOZINHO_SERVER_SEED_HEX="$(openssl rand -hex 32)" \
  uv run uvicorn chitaozinho_api.main:app --reload --no-access-log
```

Apply database migrations before starting a new environment:

```sh
uv run alembic upgrade head
```

The opt-in persistence smoke test is:

```sh
CHITAOZINHO_RUN_SERVICE_INTEGRATION=1 \
  uv run pytest apps/api/tests/test_services_integration.py
```

Local development uses the built-in development identity. Public environments
require the magic-link, secure-cookie and owner-isolation flow documented in
[`docs/authentication.md`](../../docs/authentication.md). The Railway beta uses
the Resend HTTP API; startup fails closed when its public configuration is
incomplete.
