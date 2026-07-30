# Chitãozinho

Plataforma de captura e preservação de evidências digitais.

O contrato do produto está em [SPEC.md](SPEC.md) e o progresso verificável em
[ACEITE.md](ACEITE.md).

## Desenvolvimento

```sh
nix develop
uv sync
pnpm install
scripts/check
```

`scripts/check` executa formatação, lint, typecheck e testes para TypeScript,
Python e Rust.

Para iniciar PostgreSQL 17 e Garage 1.3 localmente:

```sh
nix develop --command ./scripts/local-services start
set -a
source .env.local-services
set +a
```

As credenciais geradas ficam no arquivo ignorado `.env.local-services`. Encerre
os serviços com `nix develop --command ./scripts/local-services stop`.

Operação e recuperação estão documentadas em
[`docs/runbooks.md`](docs/runbooks.md).
