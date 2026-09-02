# Chitãozinho

O Chitãozinho é uma plataforma aberta para capturar, preservar e verificar
evidências digitais. A extensão Chromium registra a navegação; a API recebe os
artefatos e emite recibos; os verificadores conferem o pacote sem depender do
backend que o produziu.

O ambiente público atual é um **beta para dados não críticos**. Os objetos são
armazenados por 30 dias no Railway Bucket, sem Object Lock ou garantia de
imutabilidade. O estado correto nesse ambiente é `stored`, nunca `locked`.

- [Especificação normativa](SPEC.md)
- [Decisões e critérios de aceite](ACEITE.md)
- [Metodologia em linguagem simples](docs/methodology.md)
- [Índice da documentação](docs/README.md)
- [Releases](https://github.com/pmarkun/chitaozinho/releases)

## Começar a desenvolver

O ambiente suportado usa Nix. A partir da raiz do repositório:

```sh
nix develop
uv sync --all-packages --frozen
pnpm install --frozen-lockfile
./scripts/check
```

`scripts/check` executa formatação, lint, typecheck, testes de TypeScript,
Python e Rust, testes de navegador, migrações, reprodutibilidade da extensão e
validações de infraestrutura.

Para testar com PostgreSQL 17 e Garage S3 reais:

```sh
nix develop
./scripts/local-services start
./scripts/test-service-integration
CHITAOZINHO_BACKUP_SYNTHETIC=1 ./scripts/test-postgres-backup-restore
./scripts/local-services stop
```

As credenciais locais são geradas em `.env.local-services`, que não é
versionado. Os testes de integração criam bancos isolados e não reutilizam o
banco de desenvolvimento.

## Estrutura

| Caminho | Responsabilidade |
| --- | --- |
| `apps/extension/` | Extensão Chromium de captura |
| `apps/api/` | API, worker, expiração e processamento OpenTimestamps |
| `apps/verifier-cli/` | Verificador offline completo em Rust |
| `apps/verifier-web/` | Verificador local ao navegador, online ou offline |
| `packages/` | Schemas e implementações compartilhadas do protocolo |
| `test-vectors/` | Vetores criptográficos entre linguagens |
| `infra/` | OpenBao, Ceph, monitoramento e apoio ao deploy |
| `.railway/railway.ts` | Topologia declarativa do beta no Railway |
| `scripts/` | Entrada para testes, operação, release e manutenção |

## Fluxos principais

- Para executar ou diagnosticar serviços, veja
  [operações](docs/operations.md).
- Para autenticação por magic link e Resend, veja
  [autenticação](docs/authentication.md).
- Para publicar ou recuperar o beta, veja
  [deploy no Railway](docs/deployment-railway.md).
- Para conferir um pacote, veja [verificação](docs/verification.md).
- Para revisar ameaças e limites das garantias, veja
  [segurança](docs/security.md).
- Para produzir uma release reproduzível e assinada, veja
  [releases](docs/releases.md).

## Verificador web

```sh
nix develop --command pnpm --filter @chitaozinho/verifier-web build
python -m http.server 4174 --directory apps/verifier-web/dist
```

Abra <http://127.0.0.1:4174>. O pacote selecionado permanece no navegador. O
mesmo build está disponível em
<https://verifier-web-staging.up.railway.app> e pode ser reaberto offline após
a primeira carga.

## Política de dependências

Os lockfiles de Nix, pnpm, uv e Cargo são versionados. Uma dependência de
runtime exige necessidade concreta de produto ou segurança. Atualizações
maiores ficam em mudanças isoladas e alterações do protocolo devem passar por
todos os vetores entre linguagens. Dependências abandonadas ou com
vulnerabilidades críticas sem correção não são aceitas.

`@noble/hashes` é mantido para calcular SHA-256 incremental na extensão sem
concatenar uma gravação WebM inteira em memória.
