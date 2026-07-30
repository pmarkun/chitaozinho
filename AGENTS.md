# AGENTS.md


## Estrutura inicial

- Organize aplicações em `apps/`, código compartilhado em `packages/`, infraestrutura em `infra/`, documentação em `docs/` e vetores de teste em `test-vectors/`.
- Mantenha schemas e formatos de evidência versionados e compatíveis com o verificador offline.
- Faça mudanças pequenas e evite abstrações ou serviços antes de haver necessidade comprovada.

## Ambiente e dependências

- Use `nix develop` como entrada padrão do ambiente de desenvolvimento.
- Para Python, use `uv`; não use `pip` diretamente.
- Mantenha o desenvolvimento local e reproduzível. Segredos devem ficar fora do repositório.
- Não adicione dependências sem justificar a necessidade e avaliar manutenção e segurança.

## Desenvolvimento e Git

- Trabalhe em branches descritivas; não faça push direto para branches protegidas.
- Faça commits atômicos, com mensagens convencionais e uma única intenção por commit.
- Preserve mudanças existentes que não façam parte da tarefa.
- Antes de finalizar, revise o diff e rode testes, lint, typecheck e build relevantes.

## Segurança e integridade

- Nunca sobrescreva artefatos originais; transformações geram novos arquivos e hashes.
- Use serialização determinística para todo conteúdo assinado ou hasheado.
- Não publique conteúdo ou dados pessoais em blockchain.
- Cubra falhas e adulterações com testes explícitos, incluindo alteração, remoção, duplicação e reordenação.
- Migrações irreversíveis, mudanças de retenção, secrets e ações em produção exigem confirmação.

## Deploy

- Use serviços locais durante o desenvolvimento.
- Quando houver autorização para produção, publique os serviços no Railway com configuração declarativa e variáveis de ambiente.
- Antes de publicar, valide migrações, persistência, storage compatível com Object Lock, observabilidade e rollback.
- Nunca faça deploy em produção sem pedido explícito.
