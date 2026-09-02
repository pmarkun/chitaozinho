# Runbooks operacionais

Use staging e conteúdo sintético em todo ensaio. Restore, rotação de chave,
rollback de deploy e qualquer ação em produção exigem autorização explícita.

## Triagem inicial

1. Consulte `/healthz`; falha indica processo indisponível.
2. Consulte `/readyz`; `503` indica PostgreSQL, storage ou chave fixada no
   OpenBao Transit indisponível ou divergente.
3. Correlacione pelo `job_id` ou `session_id`, nunca por e-mail, token ou
   conteúdo capturado.
4. Preserve logs, audit events e objetos existentes antes de intervir.

## TSA RFC 3161

- Antes da produção, aplique o gate de seleção em
  [`tsa-evaluation.md`](tsa-evaluation.md); credenciamento não substitui o
  ensaio de interoperabilidade e a revisão contratual.
- Confirme URL, CA e CRL configuradas e valide o `.tsq` preservado.
- Não gere outro hash: retries reutilizam o `manifest_hash` e criam nova
  tentativa auditada.
- Reinicie o worker apenas após verificar banco e conectividade da TSA.
- Falhas usam backoff exponencial persistido, de 5 segundos até 1 hora por
  padrão; não altere `available_at` para forçar um loop de tentativas.
- Uma TSA indisponível mantém a captura verificável com estado temporal
  pendente ou falho; nunca altere o manifesto.

## OpenTimestamps

- O `ots-processor` roda a cada 15 minutos, agrupa até 100 manifests com salt
  numa raiz Merkle e submete somente a raiz aos calendários públicos Alice,
  Bob, Finney e Catallaxy. O serviço não usa conta, API key ou calendário
  próprio.
- Preserve o `.ots` inicial no Bucket. Cada atualização gera um complemento e
  uma attestation novos, sem substituir a prova anterior.
- `pending_confirmation` significa que os calendários ainda não devolveram a
  ligação a um bloco. `bitcoin_attestation_available` significa que essa prova
  já está no complemento, mas o servidor não declarou verificação independente
  da cadeia. Somente um `ots verify` bem-sucedido contra Bitcoin Core promove
  o lote a `confirmed`.
- Se calendários estiverem indisponíveis, o job persistente aplica backoff e
  tenta novamente; não publique hashes de sessão individuais.
- Provas de associação por sessão seguem a expiração de 30 dias. Raízes Merkle
  e `.ots` compartilhados podem ser preservados sem revelar o manifest de uma
  sessão isolada.

## Storage

- Verifique bucket, versionamento, Object Lock, modo `COMPLIANCE`, retenção,
  version ID, criptografia e metadado SHA-256.
- Nunca tente remover ou reduzir a retenção de um objeto bloqueado.
- Se a proteção final falhar, mantenha `retention_failed`; não promova o estado
  para `locked`.
- Garage é somente desenvolvimento. Evidência de staging/produção permanece no
  Ceph RGW externo, não em volume Railway.

Em falta de disco local, interrompa novos testes, preserve `data/` e confirme o
filesystem afetado antes de liberar espaço recuperável. Nunca apague partes,
pacotes, provas, banco ou audit trail para recuperar capacidade.

## PostgreSQL, backup e restore

- Antes de migração, registre `alembic current` e produza backup consistente.
- Valide o backup restaurando em uma instância isolada, executando
  `alembic upgrade head` e o smoke test de leitura.
- Aponte staging para o restore somente após comparar contagens, audit chain e
  jobs. Nunca restaure por cima da instância original.
- Migrações são revertidas uma revisão por vez em staging; dados append-only não
  são reescritos.
- O ensaio local/CI usa `scripts/test-postgres-backup-restore`: ele faz
  `pg_dump`, restaura em banco temporário, compara tabelas, contagens e digest
  do conteúdo, valida criptograficamente a cadeia de auditoria e executa as
  migrações. O banco de origem permanece somente leitura durante o ensaio.
  No CI, `CHITAOZINHO_BACKUP_SYNTHETIC=1` cria e remove também uma origem
  sintética isolada, evitando depender de qualquer banco preexistente.

## Rotação e revogação de chaves

- Gere raiz offline e certificado operacional com `scripts/key-management`.
- Publique certificado e snapshot cumulativo de revogação assinados antes de
  ativar a nova chave operacional.
- Verifique um pacote sintético com a raiz offline e com a lista de revogação
  mais recente.
- Chave comprometida é revogada; não é apagada do histórico verificável.

## Railway e rollback

- Faça deploy primeiro em staging e aguarde `/readyz`.
- Antes da promoção, gere evidência read-only de TLS, health, métricas e
  autenticação. O probe exige TLS 1.2 ou 1.3 e confirma que TLS 1.0 e 1.1 são
  recusados:

  ```sh
  nix develop --command python scripts/check-public-environment.py \
    --base-url https://api-staging.example \
    --metrics-token "$CHITAOZINHO_METRICS_TOKEN" \
    --output /tmp/chitaozinho-public-environment.json
  ```

- Execute migração e smoke funcional antes de promover a mesma imagem.
- Em falha de aplicação, restaure a versão anterior da imagem; em falha de
  dados, use apenas o restore isolado validado.
- Railway executa API e worker. Evidências finais continuam no Ceph RGW externo.
