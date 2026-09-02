# OpenBao Transit

Staging e produção assinam diretamente com uma chave Ed25519 não exportável no
OpenBao Transit. O runtime pode apenas ler a chave pública e solicitar
assinaturas; criação, rotação, exportação e exclusão não fazem parte da policy.

Em uma instância autorizada:

```sh
bao secrets enable transit
bao write transit/keys/chitaozinho-server \
  type=ed25519 \
  derived=false \
  exportable=false \
  allow_plaintext_backup=false
bao policy write chitaozinho-signing-runtime \
  infra/openbao/signing-runtime-policy.hcl
```

Use autenticação de máquina por AppRole, com RoleID e SecretID separados para
API e worker. A aplicação faz login, guarda o token de lease apenas em memória,
renova quando permitido e falha fechada se não conseguir autenticar. Token
estático é aceito somente no desenvolvimento e nos testes.

Configure endpoint HTTPS, CA interna, RoleID, SecretID, nome e versão exata da
chave nas variáveis `CHITAOZINHO_OPENBAO_*`. Credenciais são secretas, mas a
chave privada nunca sai do OpenBao.

Antes de ativar uma versão, leia sua chave pública, emita o certificado com a
raiz offline e configure a versão explicitamente. Para rotacionar: crie uma nova
versão, emita e publique o certificado e a lista de revogações, atualize
staging, valide um pacote e só então promova produção. Não habilite exclusão ou
exportação de material privado.
