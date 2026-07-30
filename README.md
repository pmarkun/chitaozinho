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
