# Créditos e Termos de Uso — verificação de 2026-10-01

## Escopo

Atualizações aprovadas do Google Docs: realizadores e parceria com Conectas,
logos fornecidos, ajustes editoriais, página `/termos-de-uso` e aceite separado
antes de cada nova captura. Texto dos termos compartilhado com a página offline
da extensão; versão 2026-10-01 registrada no evento local `capture_started`.
CTRL+Z permanece como crédito textual porque seu logo não veio na pasta.

## Resultados

- Formatação, lint, TypeScript e builds do site e da extensão passaram em Nix.
- Unitários: site 35 passaram; extensão 37 passaram, 1 ignorado.
- Site: 13 testes de navegador passaram, 2 ignorados por dependerem de ZIPs
  externos opcionais. Home, termos e privacidade passaram em Chromium, Firefox
  e WebKit a 1280 × 900 e 360 × 800, com navegação por teclado, foco, imagens
  carregadas, ausência de overflow horizontal e auditoria automática WCAG.
- Termos acessíveis no domínio principal simulado; início segue em construção.
- Extensão: 6 testes de acessibilidade passaram, 1 exclusivo do modo anônimo
  ignorado no build de magic-link. Aceite testado a 360 × 420: ambos os campos
  obrigatórios, teclado, leitura em outra aba, envio da versão e reset ao iniciar
  nova captura. Estados da captura e seleção de fonte também passaram a 360 ×
  420 e 360 × 640.
- Extensão real isolada: termos empacotados abriram com internet desligada;
  versões ausente e obsoleta foram recusadas antes de qualquer requisição à API;
  versão aceita registrada localmente; conteúdo não enviado ao servidor;
  ZIP validado pela CLI com `integral_but_incomplete` e duas lacunas declaradas
  na coleta sintética, sem ocultar a incompletude.
- Chrome conectado: logos e termos inspecionados em 1440 × 900 e 390 × 844;
  termos também conferidos a 768 × 1024. Sem overflow, logos quebrados ou
  avisos/erros de console nas páginas inspecionadas.

## Comandos

```sh
nix develop --command pnpm --filter @chitaozinho/extension --filter @chitaozinho/verifier-web format
nix develop --command pnpm --filter @chitaozinho/extension --filter @chitaozinho/verifier-web lint
nix develop --command pnpm --filter @chitaozinho/extension --filter @chitaozinho/verifier-web typecheck
nix develop --command pnpm --filter @chitaozinho/extension --filter @chitaozinho/verifier-web test
nix develop --command pnpm --filter @chitaozinho/extension --filter @chitaozinho/verifier-web build
nix develop --command pnpm --filter @chitaozinho/verifier-web test:e2e
nix develop --command env CHITAOZINHO_EXTENSION_E2E_PORT=4193 playwright test --config apps/extension/playwright.config.cjs accessibility.pw.cjs
nix develop --command bash scripts/test-hash-only-capture
```

A matriz completa da extensão usou configuração temporária equivalente na
porta 4193, pois 4173 estava ocupada. O fluxo novo foi novamente validado usando
o override de porta agora suportado pelo arquivo de configuração do projeto.

## Limites

Não houve deploy, merge nem envio à Chrome Web Store. Safari/iOS, Android,
Windows/Edge e outros dispositivos físicos não foram testados. A verificação
do ZIP usa captura sintética, sem validar Zoom ou áudio de dispositivos reais.
Nenhuma mudança de protocolo, migração, segredo ou retenção foi realizada.
O Dockerfile do site copia também o conteúdo compartilhado dos termos; a imagem
de produção não foi construída nesta validação local.
A nova rota foi incluída no seletor da Content-Security-Policy. O comando
`nix develop --command caddy validate --config infra/railway/verifier-web.Caddyfile --adapter caddyfile`
não pôde rodar porque o ambiente não fornece `caddy`. A configuração do servidor
e o build da imagem precisam ser validados antes de publicar.
