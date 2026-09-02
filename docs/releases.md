# Releases

As versões publicadas estão em
[github.com/pmarkun/chitaozinho/releases](https://github.com/pmarkun/chitaozinho/releases).
O histórico resumido fica no [`CHANGELOG.md`](../CHANGELOG.md).

Uma tag `vX.Y.Z` deve coincidir com as versões compartilhadas de Rust, Python e
extensão. O workflow gera, a partir de checkout limpo:

- binário Linux do verificador;
- ZIP da extensão descompactada;
- ZIP do verificador web estático, online e offline;
- arquivo OCI da API;
- SBOM SPDX JSON de cada artefato e das dependências da fonte;
- checksums SHA-256.

Cada artefato, SBOM e checksum recebe um bundle Sigstore criado com
`cosign sign-blob` e a identidade OIDC do GitHub. Não existe chave duradoura de
release no GitHub ou no Railway. O consumidor confere identidade, repositório e
workflow com `cosign verify-blob` e o `.sigstore.json` adjacente.

Para gerar localmente em um diretório novo e vazio:

```sh
nix develop --command ./scripts/build-release-artifacts \
  /tmp/chitaozinho-release
```

O workflow publica somente tags imutáveis e não faz deploy no Railway. Deploy é
uma operação separada.

Staging e produção configuram `CHITAOZINHO_SOFTWARE_COMMIT` com o commit exato
e `CHITAOZINHO_SOFTWARE_BUILD_HASH` com o digest `sha256:` da imagem promovida.
Ambientes públicos recusam identidades de desenvolvimento, desconhecidas ou
zeradas, mantendo cada manifesto vinculado ao build efetivamente implantado.
