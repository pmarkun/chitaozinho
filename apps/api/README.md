# API

FastAPI service for capture sessions, durable receipts and package generation.

Unit tests use SQLite and filesystem storage. For the local integration profile,
start PostgreSQL and Garage from the repository root, then load its environment:

```sh
nix develop --command ./scripts/local-services start
set -a; source .env.local-services; set +a
CHITAOZINHO_SERVER_SEED_HEX="$(openssl rand -hex 32)" \
  uv run uvicorn chitaozinho_api.main:app --reload
```

The opt-in persistence smoke test is:

```sh
CHITAOZINHO_RUN_SERVICE_INTEGRATION=1 \
  uv run pytest apps/api/tests/test_services_integration.py
```
