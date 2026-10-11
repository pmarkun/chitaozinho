# Validador web

A home apresenta Evidências e oferece o ZIP beta com instruções de
instalação manual. O download aponta para o artefato imutável da release no
GitHub, onde também ficam o bundle Sigstore e o arquivo SHA256SUMS.
Ao atualizar a versão, atualize também o link, o texto e o teste de download.
Essa release exibe Evidências e suporta guarda local: o servidor registra hashes,
enquanto a extensão monta o pacote com os arquivos locais.

O rodapé apresenta o nome do produto e links para privacidade e termos de uso.
A home do beta apresenta CTRL+Z, Coding Rights, Instituto da Hora, Sleeping
Giants e Neisser & Advogados Associados como realizadores, em parceria com
Conectas Direitos Humanos. Os logos fornecidos estão em `public/logos/`;
O logo da CTRL+Z foi obtido diretamente no site oficial da organização.
O domínio principal mantém a página em construção, com as páginas públicas
de privacidade e `/termos-de-uso` acessíveis.
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
