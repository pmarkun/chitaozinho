# Chitãozinho

Plataforma de captura e preservação de evidências digitais.

O contrato do produto está em [SPEC.md](SPEC.md) e o progresso verificável em
[ACEITE.md](ACEITE.md).

## Desenvolvimento

```sh
nix develop
uv sync --all-packages
pnpm install
scripts/check
```

`scripts/check` executa formatação, lint, typecheck e testes para TypeScript,
Python e Rust.

Para iniciar PostgreSQL 17 e Garage 1.3 localmente:

```sh
nix develop
./scripts/local-services start
set -a
source .env.local-services
set +a
```

As credenciais geradas ficam no arquivo ignorado `.env.local-services`. Encerre
os serviços com `./scripts/local-services stop`, ainda dentro do ambiente Nix.
Para validar as integrações sem reutilizar ou alterar o banco de desenvolvimento:

```sh
./scripts/test-service-integration
```

Operação e recuperação estão documentadas em
[`docs/runbooks.md`](docs/runbooks.md).
A comparação obrigatória de autoridades de carimbo do tempo antes da produção
está em [`docs/tsa-evaluation.md`](docs/tsa-evaluation.md).

O validador web local pode ser iniciado com:

```sh
nix develop --command pnpm --filter @chitaozinho/verifier-web build
python -m http.server 4174 --directory apps/verifier-web/dist
```

Abra `http://127.0.0.1:4174`. Os pacotes selecionados permanecem no navegador.

O mesmo build está publicado em staging:
<https://verifier-web-staging.up.railway.app>. A validação continua local ao
navegador e o service worker permite reabrir a aplicação offline.
