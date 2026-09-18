# Validador web

A home apresenta Evidências e oferece o ZIP beta com instruções de
instalação manual. `public/downloads/` contém o artefato original da release
v0.1.1 e seu bundle Sigstore, sem reempacotar. O SHA-256 do ZIP é
`1fe25883d7f4f650386430a8ebf21750394b809947b0788b0846b6fd23e5f4aa`.
Ao atualizar a versão, atualize também o link, o texto e o teste de download.
O arquivo é servido pelo próprio site, sem depender da navegação pelo GitHub.
Essa release ainda exibe o codinome Chitãozinho; a marca Evidências está no
código da extensão e entrará no download após uma nova release assinada.

O rodapé contém somente Conectas. O logo original é servido localmente de
`public/brand/conectas.svg`, obtido de
https://conectas.org/wp-content/uploads/2021/04/logo-conectas-portugues-1.svg.
Nomes internos, identificadores e formatos assinados continuam compatíveis.

O mesmo build estático funciona pelo link público e offline após a primeira
carga. ZIP principal, checksum e complemento são lidos somente no navegador;
o validador não envia os arquivos nem possui endpoint de upload.

```sh
nix develop --command pnpm --filter @chitaozinho/verifier-web build
nix develop --command pnpm --filter @chitaozinho/verifier-web test:e2e
python -m http.server 4174 --directory apps/verifier-web/dist
```

A validação web cobre estrutura segura, índice e manifesto assinados, hashes de
todos os membros e artefatos, cadeia de eventos, recibos, `capture_close`,
checksum e vínculo assinado do complemento probatório. A verificação
criptográfica completa dos tokens RFC 3161 e OpenTimestamps está disponível na
CLI, complementando a conferência imediata feita pelo navegador.
