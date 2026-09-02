# Operações

Use staging e conteúdo sintético nos ensaios. Restore, rotação de chave,
rollback de deploy e qualquer ação em produção exigem autorização explícita.
Os comandos disponíveis estão catalogados em [`scripts/README.md`](../scripts/README.md).

## Triagem inicial

1. Consulte `/healthz`; falha indica que o processo da API não está vivo.
2. Consulte `/readyz`; `503` indica PostgreSQL, storage ou chave do OpenBao
   indisponível ou divergente.
3. Correlacione por `job_id` ou `session_id`, nunca por e-mail, token ou
   conteúdo capturado.
4. Preserve logs, eventos de auditoria e objetos antes de intervir.

O verificador web possui seu próprio `/health`. Ele não representa a prontidão
das dependências da API.

## Storage e retenção

Existem três contratos distintos:

| Ambiente | Storage | Estado | Retenção |
| --- | --- | --- | --- |
| Desenvolvimento | filesystem ou Garage S3 | `stored` | reversível |
| Beta Railway | Railway Bucket | `stored` | 30 dias, sem imutabilidade |
| Produção probatória futura | Ceph RGW | `locked` somente após verificação | Object Lock `COMPLIANCE` |

No beta, o expirador roda diariamente às 03:15 UTC. Ele remove os prefixos da
sessão, confirma que ficaram vazios e somente então grava `expired`. Uma falha
parcial resulta em `expiration_failed`, fica auditada e é tentada novamente.
Downloads expirados respondem HTTP 410.

No modo Ceph, a API usa chave baseada em conteúdo, solicita criptografia e
Object Lock e confere hash, tamanho, version ID, modo e data de retenção com
`HeadObject`. Qualquer divergência permanece `retention_failed`; nunca promova
manualmente o estado para `locked` nem reduza a retenção de um objeto.

Garage é somente uma dependência local para testar o protocolo S3. Em falta de
disco, preserve `data/` e determine o filesystem afetado antes de liberar
espaço. Não apague partes, pacotes, provas, banco ou audit trail para recuperar
capacidade.

## PostgreSQL, backup e restore

- Antes de uma migração, registre `alembic current` e produza backup
  consistente.
- Restaure em uma instância isolada, rode `alembic upgrade head` e valide
  leitura, contagens, cadeia de auditoria e jobs.
- Nunca restaure por cima da instância original.
- Reverta migrações uma revisão por vez em staging; não reescreva dados
  append-only.

O ensaio automatizado usa `scripts/test-postgres-backup-restore`. Ele faz
`pg_dump`, restaura em banco temporário, compara tabelas, contagens e digest do
conteúdo, valida a cadeia de auditoria e executa as migrações. Com
`CHITAOZINHO_BACKUP_SYNTHETIC=1`, também cria e remove uma origem sintética.

## OpenBao e gestão de chaves

Produção e staging usam uma raiz Ed25519 offline para certificar chaves
operacionais de curta duração. A chave operacional fica não exportável no
OpenBao Transit; a aplicação recebe apenas a chave pública e envia o digest
separado por domínio para assinatura.

Gere a raiz somente em máquina offline e criptografada:

```sh
nix develop --command scripts/key-management generate-root \
  --output-dir /secure/offline/chitaozinho-root \
  --key-id root-2026-01
```

`root.seed` não pode entrar no repositório, Railway, logs ou backups online.
Publique `root-public.json` por um canal controlado independentemente.

Emita certificados operacionais por no máximo 90 dias usando a chave pública
obtida do Transit:

```sh
nix develop --command scripts/key-management issue-operational \
  --root-seed-file /secure/offline/chitaozinho-root/root.seed \
  --root-key-id root-2026-01 \
  --operational-key-id server-2026-q3 \
  --operational-public-key-hex "$SERVER_PUBLIC_KEY_HEX" \
  --valid-from 2026-07-30T00:00:00Z \
  --valid-until 2026-10-28T00:00:00Z \
  --output server-2026-q3.certificate.json
```

Revogações são snapshots cumulativos, de sequência crescente e assinados pela
raiz. Nunca sobrescreva uma lista publicada. Staging e produção recusam iniciar
sem certificado correspondente e snapshot válido. Cada pacote preserva ambos.
Veja o bootstrap e a policy mínima em [`infra/openbao/README.md`](../infra/openbao/README.md).

## TSA RFC 3161

Antes da produção, escolha uma ACT usando o cadastro oficial do ITI e um ensaio
comparável. Credenciamento não substitui interoperabilidade ou revisão
contratual. O gate exige:

- endpoint RFC 3161 que aceite TSQ e devolva TSR para SHA-256;
- nonce, `genTime`, policy OID, certificado e cadeia verificáveis;
- CRL ou OCSP e trust store versionado;
- TLS moderno, autenticação documentada e ambiente de teste;
- contrato compatível com LGPD, retenção de logs e resposta a incidentes;
- SLA, limites, suporte, portabilidade e custo formalizados.

Envie o mesmo hash sintético às candidatas e preserve TSQ, TSR, cadeia,
política, latência e resultado. Produção só avança com interoperabilidade,
trust store e contrato aprovados. Retries reutilizam o `manifest_hash`, criam
tentativa auditada e usam backoff persistente; uma falha nunca altera o
manifesto.

## OpenTimestamps

O `ots-processor` roda a cada 15 minutos, agrupa até 100 manifests com salt em
uma raiz Merkle e envia somente a raiz aos calendários públicos configurados.
Ele não usa conta, API key ou calendário próprio.

Preserve o `.ots` inicial. Cada atualização gera complemento e attestation
novos, sem substituir a prova anterior:

- `pending_confirmation`: ainda não há ligação a um bloco;
- `bitcoin_attestation_available`: a ligação está presente, mas não foi
  verificada pelo servidor contra uma cadeia independente;
- `confirmed`: `ots verify` concluiu com sucesso contra Bitcoin Core.

Calendários indisponíveis acionam backoff persistente. Nunca publique hashes de
sessões individuais. Provas de associação seguem a expiração da sessão; raízes
Merkle compartilhadas podem ser preservadas sem revelar um manifesto isolado.

## Railway e rollback

- Faça deploy primeiro em staging e aguarde `/readyz`.
- Gere evidência somente leitura de TLS, health, métricas e autenticação com
  `scripts/check-public-environment.py`.
- Execute migrações e smoke funcional antes de promover a mesma imagem.
- Em falha da aplicação, restaure a imagem anterior.
- Em falha de dados, use apenas um restore isolado já validado.
- Não apague PostgreSQL, Bucket ou volume do OpenBao durante rollback.
- Se o OpenBao estiver selado, deixe a assinatura indisponível; não use seed
  local como fallback.

## Desempenho da captura

Compare a mesma página e perfil do Chrome em repouso e durante uma captura:

```sh
nix develop --command scripts/measure-browser-resources \
  baseline 30 /tmp/chitaozinho-performance.csv
nix develop --command scripts/measure-browser-resources \
  capture 75 /tmp/chitaozinho-performance.csv
nix develop --command uv run python scripts/analyze_browser_resources.py \
  /tmp/chitaozinho-performance.csv \
  --output /tmp/chitaozinho-performance-report.json
```

No beta, investigue antes do aceite se a captura acrescentar mais de 25 pontos
percentuais médios de CPU, 250 MiB de pico RSS ou 100 MiB de escrita por minuto,
ou se a página deixar de responder. Registre máquina, Chrome, página, resultado
e hash do CSV na evidência do ensaio, não neste repositório.
