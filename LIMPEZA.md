# Limpeza do repositório

Checklist concluído em 2 de setembro de 2026 para tornar o Chitãozinho mais
simples de entender, operar e modificar por novos colaboradores, sem alterar
funcionalidades, formatos de evidência ou garantias cobertas por testes. As
etapas foram mantidas separadas por tema na mesma branch de limpeza.

## Princípios

- [x] Fazer mudanças pequenas, revisáveis e separadas por intenção.
- [x] Não misturar limpeza documental com mudanças de comportamento.
- [x] Usar o histórico do Git como arquivo; não criar uma pasta de documentos
      legados sem utilidade operacional.
- [x] Remover documentos antigos depois de preservar apenas as decisões ainda
      relevantes.
- [x] Não enfraquecer, apagar, pular ou marcar testes como ignorados para fazer
      a limpeza passar.
- [x] Preservar mudanças locais e arquivos ignorados dos ambientes dos
      colaboradores.

## Superfícies protegidas

Estas áreas não devem sofrer alterações funcionais durante a limpeza:

- [x] Schemas e versões dos formatos de evidência.
- [x] Serialização canônica, hashes, assinaturas e recibos.
- [x] Vetores criptográficos e verificadores offline.
- [x] Migrações de banco de dados.
- [x] Retenção e estados de persistência.
- [x] Integrações com OpenBao e OpenTimestamps.
- [x] Configuração declarativa do Railway e seus validadores.
- [x] Build reproduzível, SBOM, Sigstore e processo de release.

## Etapa 1 — Higiene mecânica

### Inventário e linha de base

- [x] Criar uma branch dedicada à limpeza.
- [x] Confirmar que o worktree parte de um estado conhecido e limpo.
- [x] Registrar a lista de arquivos versionados e ignorados.
- [x] Rodar `nix develop --command ./scripts/check` antes das remoções.
- [x] Rodar a integração PostgreSQL/Garage antes das remoções.
- [x] Registrar qualquer falha já existente para não atribuí-la à limpeza.

### Artefatos gerados

- [x] Confirmar que `apps/extension/test-results/.last-run.json` não está no Git.
- [x] Confirmar que `apps/verifier-web/test-results/.last-run.json` não está no Git.
- [x] Procurar outros caches, relatórios, logs, builds e temporários versionados.
- [x] Confirmar que resultados de Playwright e demais testes estão ignorados.
- [x] Confirmar que `.env`, secrets, bancos locais, `node_modules`, ambientes
      virtuais e diretórios de build continuam ignorados.
- [x] Adicionar uma verificação simples que rejeite artefatos gerados no Git.
- [x] Avaliar um comando de limpeza local. Decisão: não adicioná-lo, pois os
      artefatos já são ignorados e uma remoção automática criaria risco sem
      melhorar o checkout compartilhado.
- [x] Não apagar automaticamente `data/`, `secrets/` ou arquivos locais de
      colaboradores.

### Validação do PR 1

- [x] Rodar a suíte completa novamente.
- [x] Confirmar que os testes não deixam alterações no worktree.
- [x] Confirmar que nenhum arquivo necessário ao build ou à CI foi removido.

## Etapa 2 — Documentação e onboarding

### Estrutura alvo

- [x] Manter `README.md` como porta de entrada do projeto.
- [x] Manter `SPEC.md` como especificação normativa.
- [x] Manter `ACEITE.md` como registro de decisões e critérios de aceite.
- [x] Atualizar `CHANGELOG.md` com as releases publicadas e `Unreleased`.
- [x] Criar `docs/README.md` como índice curto da documentação restante.
- [x] Reduzir `docs/` de 19 documentos para aproximadamente 8 documentos úteis.

Estrutura desejada:

```text
README.md
SPEC.md
ACEITE.md
CHANGELOG.md
docs/
├── README.md
├── authentication.md
├── deployment-railway.md
├── operations.md
├── security.md
├── verification.md
├── methodology.md
└── releases.md
```

### README e entrada no projeto

- [x] Explicar em poucas linhas o que é o Chitãozinho.
- [x] Informar o estado e as limitações do beta.
- [x] Adicionar um caminho curto para instalar dependências, rodar e testar.
- [x] Incluir um mapa de `apps/`, `packages/`, `infra/`, `scripts/` e
      `test-vectors/`.
- [x] Explicar qual documento consultar para protocolo, deploy, operação,
      segurança e verificação.
- [x] Apontar para a release e para os artefatos públicos atuais.

### Consolidação e remoção

- [x] Remover `docs/comparativo-verifact.md`.
- [x] Substituir `docs/smoke-tests.md` por uma matriz curta de testes atuais.
- [x] Extrair pendências ainda válidas de `docs/security-review.md` e remover o
      relatório antigo.
- [x] Incorporar `docs/accessibility.md` aos critérios atuais de qualidade.
- [x] Incorporar `docs/capture-coverage.md` aos critérios atuais de qualidade.
- [x] Incorporar `docs/performance.md` aos critérios atuais de qualidade.
- [x] Incorporar `docs/dependencies.md` ao README ou ao guia de desenvolvimento.
- [x] Incorporar o conteúdo útil de `docs/evidence-format.md` à especificação ou
      ao guia de verificação e remover o documento curto.
- [x] Incorporar `docs/legal-limitations.md` à especificação ou a `security.md`
      e remover o documento curto.
- [x] Incorporar `docs/threat-model.md` a `security.md` e remover o documento
      curto.
- [x] Consolidar `docs/runbooks.md`, `docs/retention.md` e
      `docs/key-management.md` em `docs/operations.md` e `docs/security.md`.
- [x] Avaliar `docs/tsa-evaluation.md`: preservar uma decisão arquitetural
      resumida se ainda for relevante e remover o restante.
- [x] Renomear `docs/railway-beta.md` para `docs/deployment-railway.md` e retirar
      conteúdo duplicado.
- [x] Renomear `docs/metodologia-em-linguagem-simples.md` para
      `docs/methodology.md`, preservando a linguagem acessível.
- [x] Consolidar os documentos restantes sem repetir conteúdo normativo de
      `SPEC.md` e `ACEITE.md`.
- [x] Atualizar todas as referências antes de remover ou renomear arquivos.
- [x] Não manter cópias em `docs/history/`; recuperar versões antigas pelo Git.

### Correções de conteúdo atual

- [x] Explicar que o beta usa a API HTTP do Resend.
- [x] Explicar separadamente qualquer fallback SMTP ainda mantido para
      desenvolvimento ou compatibilidade.
- [x] Substituir referências operacionais antigas a `railway.json` por
      `.railway/railway.ts`.
- [x] Distinguir `/healthz`, `/readyz` e o healthcheck específico do verificador.
- [x] Descrever corretamente Railway Bucket como armazenamento temporário, sem
      garantia de imutabilidade ou Object Lock.
- [x] Conferir a descrição atual de OpenBao, OpenTimestamps e do processador OTS.
- [x] Marcar claramente limitações do verificador web em relação à CLI offline.
- [x] Atualizar `apps/api/README.md` para refletir a autenticação pública atual.
- [x] Reduzir `.railway/README.md` ao fluxo realmente usado pelo projeto.

### Qualidade documental

- [x] Garantir que todo documento restante seja alcançável pelo README principal
      ou por `docs/README.md`.
- [x] Adicionar verificação automática de links Markdown locais.
- [x] Procurar referências a arquivos removidos ou renomeados.
- [x] Procurar instruções conflitantes sobre SMTP, Resend, Railway, storage,
      healthchecks e retenção.
- [x] Evitar documentação que apenas repete código ou configuração declarativa.

### Validação do PR 2

- [x] Seguir o README a partir de um clone limpo.
- [x] Executar todos os comandos apresentados na documentação principal.
- [x] Rodar a verificação de links.
- [x] Rodar a suíte completa existente.

## Etapa 3 — Organização dos scripts

### Classificação

- [x] Classificar cada script como CI, Railway, desenvolvimento local, operação,
      release ou manutenção.
- [x] Localizar referências em workflows, Dockerfiles, configuração Railway,
      documentação e outros scripts.
- [x] Identificar scripts sem consumidor comprovado.
- [x] Documentar os comandos principais no README ou em uma seção curta de
      `docs/operations.md`.

### Simplificação

- [x] Remover scripts somente depois de provar que não têm consumidor.
- [x] Padronizar nomes, shebangs, tratamento de erro e mensagens de ajuda.
- [x] Remover wrappers triviais apenas quando não fizerem parte de contratos de
      execução do Docker ou Railway.
- [x] Reduzir duplicações pequenas sem criar uma nova camada abstrata.
- [x] Preservar os validadores de protocolo, Railway, OpenBao, storage,
      monitoramento e reproducibilidade.
- [x] Preservar scripts de backup, restauração, segurança, release e assinatura.

### Validação do PR 3

- [x] Rodar todos os scripts chamados pela CI.
- [x] Rodar validações de configuração de infraestrutura.
- [x] Rodar testes de integração com PostgreSQL e storage compatível com S3.
- [x] Rodar verificações de reproducibilidade da extensão, do verificador e da
      imagem OCI.
- [x] Confirmar que os comandos do Railway continuam com os mesmos contratos.

## Etapa 4 — Organização interna avaliada

Os arquivos grandes foram avaliados depois das etapas anteriores. A decisão foi
não dividi-los nesta limpeza: todos concentram fluxos coesos e sensíveis, e uma
refatoração aumentaria o risco sem melhorar o onboarding.

- [x] Identificar responsabilidades distintas nos arquivos fonte muito grandes.
- [x] Avaliar `apps/api/src/chitaozinho_api/main.py`: manter como está neste ciclo.
- [x] Avaliar o processamento de pacotes no verificador Rust: manter como está.
- [x] Avaliar o validador web: manter como está.
- [x] Avaliar o background da extensão: manter como está.
- [x] Avaliar os testes extensos de captura: manter juntos como caracterização
      do fluxo completo.
- [x] Confirmar que nenhuma API interna ou fonte de runtime foi modificada.
- [x] Confirmar que schemas, test vectors e migrações não aparecem no diff.

## Verificação final

- [x] Um colaborador novo consegue começar apenas pelo `README.md`.
- [x] Todo documento restante tem finalidade clara e está no índice.
- [x] Não existem caches, relatórios de teste ou builds versionados.
- [x] Não existem referências quebradas a documentos ou scripts removidos.
- [x] Não existem instruções operacionais conflitantes ou sabidamente antigas.
- [x] A suíte original continua verde sem redução de cobertura ou rigor.
- [x] A integração PostgreSQL/S3 continua verde.
- [x] Os vetores criptográficos continuam idênticos.
- [x] Os artefatos reproduzíveis continuam idênticos.
- [x] Nenhum schema, manifesto ou byte assinado mudou sem versionamento.
- [x] A configuração Railway passa pelos validadores sem mudança destrutiva.
- [x] Nenhum segredo aparece no Git, nos logs ou nos artefatos.
- [x] Cada PR documenta arquivos removidos, conteúdo consolidado, testes rodados
      e riscos não validados.

## Fora do escopo

- [x] Não alterar funcionalidades do produto.
- [x] Não alterar contratos públicos da API.
- [x] Não alterar o formato dos pacotes de evidência.
- [x] Não trocar dependências ou arquitetura sem necessidade comprovada.
- [x] Não executar migrações destrutivas.
- [x] Não alterar secrets ou dados de staging/produção.
- [x] Não fazer deploy ou merge como consequência automática da limpeza.

## Evidências da execução

- [x] Linha de base antes da limpeza: `./scripts/check` passou, com 105 testes
      Python aprovados, 3 integrações opt-in puladas, testes TypeScript e Rust,
      Playwright, migrações e validadores verdes.
- [x] Linha de base de serviços: integração PostgreSQL/Garage e ensaio de
      backup/restore passaram em bancos isolados.
- [x] Depois da limpeza: `./scripts/check` passou novamente com a mesma matriz.
- [x] Integração final PostgreSQL/Garage: 3 testes aprovados; backup restaurado
      com 18 tabelas e revisão `0006_beta_retention`.
- [x] Auditoria final: OSV e Trivy passaram sem segredo ou misconfiguração.
- [x] Verificador reproduzível:
      `bd4cd83283302429170e902c115103b07c22420d172ec3892ab8803e1b442fa3`.
- [x] Imagem OCI reproduzível:
      `sha256:820f0160f9fa745af78d3f4b1d0509f4adbd3034cd50516307d1f93da3afe6a7`.
- [x] Documentação reduzida de 19 para 8 arquivos em `docs/`.
- [x] Guard de higiene incorporado ao gate principal e executado com sucesso.
