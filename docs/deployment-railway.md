# Deploy do beta no Railway

Este ambiente é um beta para dados não críticos. Desde a release 0.1.2, novas
capturas usam guarda local: arquivos não são enviados ao servidor. Objetos
legados no Railway Bucket mantêm a retenção original de 30 dias, sem
imutabilidade. Nenhum perfil Railway pode alegar Object Lock ou proteção WORM.

## Serviços

### Transição para guarda local (`hash_only`)

A configuração declarativa define `CHITAOZINHO_EVIDENCE_MODE=hash_only`.
Esse perfil não cria objetos de evidência nem ZIPs de captura no servidor. O
Bucket continua contendo comprovantes criptográficos (hashes, Merkle/OTS),
não o conteúdo de novas capturas. Autenticação, recibos e metadados técnicos
continuam no PostgreSQL; isso não elimina a necessidade de uma política de dados.

1. Publique a migração aditiva `0007_hash_only`; sessões existentes continuam
   `remote`. Não remova buckets, volumes, backups ou registros legados.
2. Teste a nova extensão e API juntas antes de ativar o perfil. O ZIP assinado
   `0.1.1` é legado: não é compatível com captura só-hash; use `0.1.2` ou posterior.
3. Publique uma nova release assinada da extensão, atualize o link da home e
   só então libere o novo fluxo. Não distribua builds de desenvolvimento como releases.
4. Ative `hash_only` na API. Clientes antigos terão o upload recusado e precisarão
   atualizar. Capturas `remote` abertas não são convertidas silenciosamente.
5. Valide captura, pacote local, download repetido sem API, conferência web/CLI
   e processamento OTS. O teste local reproduzível é
   `nix develop --command bash scripts/test-hash-only-capture` (porta 8000 livre).

O módulo remoto permanece disponível com `remote`. O expirador mantém a política
original das sessões antigas; sessões só-hash não possuem expiração de arquivos
no servidor. Nenhuma exclusão de conteúdo legado faz parte da migração.
Rollback de código antigo exige suspender novas capturas só-hash; não reclassifique
esses recibos como persistência e não remova a coluna aditiva. Preserve a nova
extensão/verificadores para abrir os ZIPs locais já produzidos.

O ambiente lógico `beta` roda dentro do `staging` do Railway. Ele contém os
serviços públicos `api` e `verifier-web`; os processos privados `worker`,
`retention-cleanup` e `ots-processor`; PostgreSQL; o Bucket
`chitaozinho-beta`; e um OpenBao de nó único com volume persistente. A fonte da
topologia é [`.railway/railway.ts`](../.railway/railway.ts).

Revise toda alteração com `railway config plan` antes de usar
`railway config apply`. O plano não autoriza mudanças destrutivas.

## Segredos obrigatórios

Configure como variáveis seladas antes de considerar o beta pronto:

- API, worker e processos agendados: pepper de autenticação, token de métricas,
  chave Resend limitada ao envio, remetente verificado, AppRoles do OpenBao,
  certificado operacional assinado pela raiz, snapshot de revogação e documento
  público da raiz offline.
- OpenBao: certificado e chave TLS do servidor, vindos do cofre privado do
  operador.

O remetente do beta é `Chitãozinho <acesso@mail.arapy.ia.br>`. O domínio do
Resend é `mail.arapy.ia.br`; seus registros DKIM, SPF e MX são DNS-only na zona
Cloudflare `arapy.ia.br`. Configure o remetente completo em
`CHITAOZINHO_RESEND_FROM` somente depois que o Resend confirmar o domínio.

O certificado da CA interna é público e fica versionado em
`infra/openbao/ca.crt`. A chave da CA, a chave TLS do servidor, a chave de
assinatura da extensão, as partes Shamir, o token root e os SecretIDs de
AppRole nunca entram no Git, nos builds ou nos logs do Railway.

## Primeiro bootstrap

1. Aplique o plano de infraestrutura revisado e aguarde o OpenBao iniciar
   selado.
2. Conecte por um shell Railway ou túnel da rede privada com
   `BAO_ADDR=https://openbao.railway.internal:8200` e
   `BAO_CACERT=infra/openbao/ca.crt`.
3. Rode `infra/openbao/initialize-beta` uma vez e grave o JSON em diretório
   privado do operador. Guarde as três partes Shamir separadamente; duas são
   necessárias após cada reinício.
4. Faça unseal com duas partes. Coloque o token root inicial em `BAO_TOKEN`,
   defina uma senha forte em `OPENBAO_OPERATOR_PASSWORD` e rode
   `infra/openbao/bootstrap-beta`. O script grava AppRoles separados de API e
   worker em arquivo modo 0600 e revoga o token root inicial.
5. Leia a chave pública do Transit, emita o certificado operacional e o
   snapshot inicial de revogação com `scripts/key-management` e configure as
   variáveis. API e worker devem usar SecretIDs diferentes.
6. Faça redeploy de API e worker. `/readyz` permanece indisponível enquanto o
   OpenBao estiver selado e volta a ficar saudável após unseal, sem fallback
   para chave local.

## OpenTimestamps público

O serviço privado `ots-processor` executa `python -m
chitaozinho_api.ots_processor` a cada 15 minutos e termina após o lote. Ele usa
o PostgreSQL para coordenação e o Bucket para compartilhar provas com API e
worker; não monta volume Railway. Os documentos de confiança e credenciais
necessários são referências internas às variáveis do worker, sem duplicar seus
valores na configuração ou no Git.

O beta usa quatro calendários públicos e gratuitos, sem segredo:

- `alice.btc.calendar.opentimestamps.org`;
- `bob.btc.calendar.opentimestamps.org`;
- `finney.calendar.eternitywall.com`;
- `ots.btc.catallaxy.com`.

Sem `CHITAOZINHO_OTS_BITCOIN_NODE_URL`, o estado máximo automático é
`bitcoin_attestation_available`. Configurar um Bitcoin Core podado permite a
verificação servidor-side e a promoção para `confirmed`; isso não é necessário
para criar, atualizar, baixar ou verificar a prova em outro nó.

## Operação e rollback

- O cron diário roda às 03:15 UTC. Uma sessão totalmente removida passa para
  `expired` e seus downloads retornam HTTP 410. Exclusão parcial resulta em
  `expiration_failed` e nova tentativa no próximo ciclo.
- Ative backups diários do PostgreSQL e do volume do OpenBao. O Bucket não tem
  segunda cópia porque o beta aceita apenas dados não críticos.
- Reverta a aplicação restaurando o commit anterior e redeployando a imagem.
  Não apague banco, Bucket ou volume do OpenBao.
- Se o OpenBao estiver indisponível ou selado, mantenha a assinatura
  indisponível. Nunca adicione uma seed em texto simples como fallback.

Os procedimentos detalhados de diagnóstico, backup, chaves, storage e provas
temporais estão em [operações](operations.md).
