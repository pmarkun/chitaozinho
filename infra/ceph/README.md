# Ceph RGW

Ceph RGW é o storage de evidências fora do Railway. A versão e a imagem estão
fixadas em `version.json`; `rgw-service.json` é a especificação `cephadm`.
Garage continua sendo apenas o substituto local.

Pré-requisitos operacionais:

- cluster Ceph saudável, com hosts RGW rotulados `rgw`;
- certificado TLS confiável no RGW ou CA privada montada na aplicação;
- OpenBao/Vault configurado como backend KMS do RGW;
- usuário RGW exclusivo da aplicação, sem capacidade administrativa;
- operador do Ceph separado do processo da aplicação;
- cópia off-site/multisite antes de produção.

Aplique o serviço somente em um cluster autorizado:

```sh
ceph orch apply -i infra/ceph/rgw-service.json
```

Configure no cluster `rgw_crypt_require_ssl=true`,
`rgw_crypt_s3_kms_backend=vault` e o endereço/autenticação do OpenBao/Vault.
O valor literal `aws:kms` em chamadas S3 é o identificador definido pelo
protocolo compatível do RGW; ele não usa a AWS.

Crie cada bucket já com Object Lock habilitado. Para o ensaio isolado, use
retenção padrão de um dia em modo `COMPLIANCE`; staging e produção exigem ao
menos 90 dias. O script abaixo recusa buckets preexistentes, exige uma
confirmação explícita e produz um relatório privado:

```sh
CHITAOZINHO_PROVISION_CEPH_BUCKET=I_ACCEPT_NEW_IMMUTABLE_BUCKET \
  nix develop --command scripts/provision-ceph-bucket \
  --output /secure/reports/ceph-provisioning.json
```

Depois execute `scripts/test-s3-object-lock` com dados sintéticos e guarde
também o relatório privado.

Não aplique esta configuração nem crie buckets sem autorização explícita: a
retenção `COMPLIANCE` impede exclusão antecipada, inclusive administrativa.
