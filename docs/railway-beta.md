# Railway beta runbook

This environment is an invited beta for non-critical data. Railway Bucket
objects are stored for 30 days and are not immutable: the service must report
`stored`, never `locked`, and must not claim Object Lock or WORM protection.

## Services

The `staging` environment contains the public `api` and `verifier-web`, plus
private `worker`, `retention-cleanup`, PostgreSQL, `chitaozinho-beta` Bucket and
a single-node `openbao` with a persistent volume. Infrastructure changes are
reviewed with `railway config plan` before `railway config apply`.

## Required secrets

Set these as sealed Railway variables before considering the beta ready:

- API, worker and cleanup: authentication pepper, metrics token, Resend
  sending-only key and verified sender, OpenBao AppRole credentials, root-signed server
  certificate, revocation snapshot and offline root public document.
- OpenBao: the TLS server certificate and key from the private operator store.

The beta sender is `Chitãozinho <acesso@mail.arapy.ia.br>`. The Resend domain
is `mail.arapy.ia.br`; its DKIM, SPF and MX records are DNS-only records in the
Cloudflare `arapy.ia.br` zone. Set this full sender value in
`CHITAOZINHO_RESEND_FROM` after Resend reports the domain as verified.

The internal CA certificate is public and versioned at `infra/openbao/ca.crt`.
The CA key, TLS server key, extension signing key, Shamir shares, root token and
AppRole SecretIDs must never enter Git, build artifacts or Railway logs.

## First bootstrap

1. Apply the reviewed infrastructure plan and wait for OpenBao to start sealed.
2. Connect from a Railway shell or private-network tunnel with
   `BAO_ADDR=https://openbao.railway.internal:8200` and
   `BAO_CACERT=infra/openbao/ca.crt`.
3. Run `infra/openbao/initialize-beta` once, writing its JSON to a private
   operator directory. Store the three Shamir shares separately; two are
   required after every restart.
4. Unseal with two shares. Put the initial root token in `BAO_TOKEN`, set a
   strong `OPENBAO_OPERATOR_PASSWORD`, and run `infra/openbao/bootstrap-beta`.
   The script writes separate API and worker AppRole credentials to a mode-0600
   file and revokes the initial root token.
5. Read the Transit public key, issue the operational certificate and initial
   revocation snapshot with `scripts/key-management`, then set all application
   variables. The API and worker must use different SecretIDs.
6. Redeploy API and worker. `/readyz` must remain unavailable while OpenBao is
   sealed and become healthy after unseal without any local-key fallback.

## OpenTimestamps público

O serviço privado `ots-processor` executa `python -m
chitaozinho_api.ots_processor` a cada 15 minutos e termina após o lote. Ele usa
o PostgreSQL para coordenação e o Bucket para compartilhar provas com API e
worker; não monta volume Railway.

O beta usa quatro calendários públicos e gratuitos, sem segredo:

- `alice.btc.calendar.opentimestamps.org`;
- `bob.btc.calendar.opentimestamps.org`;
- `finney.calendar.eternitywall.com`;
- `ots.btc.catallaxy.com`.

Sem `CHITAOZINHO_OTS_BITCOIN_NODE_URL`, o estado máximo automático é
`bitcoin_attestation_available`. Configurar um Bitcoin Core podado permite a
verificação servidor-side e a promoção para `confirmed`; isso não é necessário
para criar, atualizar, baixar ou verificar a prova em outro nó.

## Operations and rollback

- Daily cron runs at 03:15 UTC. A fully deleted session becomes `expired` and
  its downloads return HTTP 410. Partial deletion becomes `expiration_failed`
  and is retried on the next run.
- Enable daily Railway backups for PostgreSQL and the OpenBao volume. Bucket
  contents have no second copy because the beta accepts non-critical data only.
- Roll back application changes by reverting the GitHub PR and redeploying the
  previous image. Do not delete the database, Bucket or OpenBao volume.
- If OpenBao is unavailable or sealed, leave signing unavailable. Never add a
  plaintext signing seed as a fallback.
