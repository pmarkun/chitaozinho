# Verificação e qualidade

## Verificador offline

A CLI Rust verifica pacotes sem autenticação, backend ou rede:

```sh
cargo run -p chitaozinho-verifier -- verify \
  chitaozinho-evidence-session.zip \
  --trusted-root-key-hex "$ROOT_PUBLIC_KEY_HEX" \
  --html-report verification.html
```

Ela recusa caminhos inseguros, symlinks, nomes duplicados e expansão suspeita;
limita entradas e memória; valida o conjunto exato de membros; recalcula hashes;
confere assinaturas, certificado operacional, revogações, cadeias, recibos e
`capture_close`; e diferencia captura completa de ausências declaradas.

Complementos temporais são append-only e podem ser fornecidos sem alterar o ZIP:

```sh
cargo run -p chitaozinho-verifier -- verify \
  evidence.zip \
  --proof-bundle proofs.zip \
  --trusted-root-key-hex "$ROOT_PUBLIC_KEY_HEX"
```

Tokens RFC 3161 válidos exigem CA e CRL explícitas. Provas OpenTimestamps
confirmadas são conferidas pelo cliente `ots`; provas ainda não confirmadas são
interpretadas e reportadas como pendentes.

## Verificador web

O build estático processa ZIP, checksum e complemento somente no navegador. A
CSP impede conexões da aplicação e o service worker permite reabrir as páginas
offline. Ele confere estrutura segura, índice, manifesto, hashes, assinaturas,
cadeias, recibos, `capture_close`, checksum e vínculo do complemento.

A verificação criptográfica completa dos tokens RFC 3161 e OpenTimestamps
permanece na CLI. A interface web deve apresentar essa limitação, sem alegar
que conferiu uma prova externa que apenas vinculou ao pacote.

## Matriz automatizada

| Área | Cobertura | Comando |
| --- | --- | --- |
| TypeScript | formato, lint, tipos, unidades e build | `pnpm -r format && pnpm -r lint && pnpm -r typecheck && pnpm -r test && pnpm -r build` |
| Extensão | popup, recuperação, acessibilidade e responsividade | `playwright test --config apps/extension/playwright.config.cjs` |
| Verificador web | desktop, mobile, offline, processamento local e WCAG | `pnpm --filter @chitaozinho/verifier-web test:e2e` |
| Python | API, auth, storage, jobs, OTS, retenção e migrações | `uv run pytest` |
| Rust | protocolo, pacotes hostis e verificação | `cargo test --workspace` |
| Serviços | PostgreSQL e Garage S3 reais | `./scripts/test-service-integration` |
| Infraestrutura | Railway, Ceph, OpenBao e monitoramento | `./scripts/check` |
| Supply chain | extensão, verificador e OCI reproduzíveis | workflows da CI |

O gate local principal é:

```sh
nix develop --command ./scripts/check
```

O teste E2E com um pacote real é opcional e usa
`CHITAOZINHO_WEB_TEST_PACKAGE`, `CHITAOZINHO_WEB_TEST_CHECKSUM` e
`CHITAOZINHO_WEB_TEST_SERVER_KEY`.

## Aceite manual da extensão

Execute o fluxo principal no Chrome/Chromium 116+ em desktop real:

- popup em 320×640 e em altura reduzida;
- zoom de 100% e 400%;
- login, captura, screenshot, marcador, finalização e download apenas por
  teclado;
- foco visível e movido ao título depois de mudanças de tela;
- leitura de títulos, labels, status, erros e resultados por leitor de tela;
- captura interrompida e retomada;
- sessão expirada, storage falho e OpenBao selado;
- ausência de overflow horizontal, erros inesperados de console ou rede.

Os testes Axe cobrem WCAG 2.0, 2.1 e 2.2 A/AA, mas não provam sozinhos a
usabilidade com leitor de tela, zoom ou extensão instalada de verdade.

## Aceite de staging

O smoke do beta deve:

- solicitar e consumir um magic link enviado pelo Resend;
- produzir uma captura sintética completa;
- observar `stored`, nunca `locked`;
- baixar e validar pacote no navegador e na CLI;
- obter e validar o complemento OpenTimestamps;
- provar falha segura com OpenBao selado e recuperação após unseal;
- executar expiração com tempo controlado e confirmar HTTP 410.

Use `scripts/smoke-railway-beta` para a parte automatizada. Registre evidências
do ensaio fora do repositório; este documento contém o contrato atual, não um
diário de execuções antigas.
