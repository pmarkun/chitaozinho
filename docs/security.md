# Segurança e limites

O modelo de ameaças normativo está na [seção 5 da especificação](../SPEC.md).
Este documento reúne os controles operacionais, as limitações que precisam ser
comunicadas e o gate automatizado atual.

## Limite da garantia

O pacote demonstra integridade e rastreabilidade técnica a partir do ponto em
que os artefatos foram observados e processados. Ele não prova autoria, verdade
material ou validade jurídica definitiva.

A captura nasce no navegador do usuário. Comprometimento anterior da conta, do
sistema operacional, do navegador, do perfil ou de outra extensão está fora da
fronteira de prova. A ausência de isolamento do dispositivo deve ser considerada
ao interpretar o pacote.

O beta Railway também não oferece WORM ou Object Lock. Seus objetos são
temporários e recebem o estado `stored`. Somente um ambiente Ceph cuja retenção
tenha sido conferida pode usar `locked`.

## Cobertura da captura

O manifesto declara o que o navegador conseguiu observar:

- o DOM principal é serializado quando scripting é permitido;
- iframes podem aparecer em vídeo e screenshots, mas os documentos internos
  não são serializados e tornam a cobertura incompleta;
- canvas e WebGL são cobertos apenas pelos pixels visíveis;
- conteúdo DRM com EME não é extraído;
- páginas protegidas do navegador preservam artefatos visuais em melhor esforço
  e declaram DOM e detecção de recursos indisponíveis.

Esses dados ficam em `capture_coverage` dentro de `capture/metadata.json` e as
lacunas materiais entram na lista assinada `known_gaps`. Uma ausência declarada
não deve ser apresentada como captura completa.

## Gestão de segredos e chaves

- Chaves raiz são geradas offline e não entram em Git, Railway ou logs.
- Staging e produção assinam com chave não exportável no OpenBao Transit.
- API e worker usam AppRoles separados e de privilégio mínimo.
- O certificado operacional e a lista cumulativa de revogações são assinados
  pela raiz e preservados no pacote.
- Tokens, cookies, e-mails e mensagens de provedores não entram na auditoria.
- Segredos de Resend, métricas, AppRoles e TLS ficam no secret store.

Os procedimentos de geração, rotação e revogação estão em
[operações](operations.md).

## Gate automatizado

Cada execução da CI analisa somente a árvore versionada:

- OSV Scanner verifica dependências Rust, Python e npm travadas;
- Trivy procura segredos e configurações de alto ou crítico risco em código,
  Docker, Ceph e workflows;
- testes negativos cobrem alteração, remoção, duplicação, reordenação, pacotes
  hostis, owner isolation e falsos estados de completude;
- builds e artefatos críticos passam por verificações de reprodutibilidade.

Execute localmente:

```sh
nix develop --command ./scripts/security-audit
```

Existe uma exceção exata para `GHSA-mh99-v99m-4gvg`, restrita à dependência
transitiva de desenvolvimento `brace-expansion@1.1.18`, porque o intervalo
agregado do OSV contradiz a correção indicada pelo advisory upstream. Qualquer
mudança de advisory, pacote ou versão exige nova revisão.

## Controles verificados no código

- Lifecycle de magic links, cookies seguros, CORS, origem contra CSRF e URLs de
  download limitadas.
- Isolamento de sessões por dono e identificadores opacos.
- Assinaturas do cliente e servidor, delegação pela raiz e revogação.
- Auditoria append-only e serialização determinística.
- Upload idempotente, limites de tamanho e confinamento do storage local.
- ZIPs hostis, traversal, symlinks, duplicação e expansão excessiva recusados.
- Logs estruturados e redigidos.
- TLS público moderno, health, readiness, métricas e configuração declarativa
  protegidos por gates.

Esses controles não substituem pentest independente, revisão humana do ambiente
implantado ou validação real de Ceph Object Lock antes de uma oferta probatória.
