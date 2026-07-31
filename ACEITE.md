# ACEITE.md

Checklist de implementação e aceite da [SPEC.md](SPEC.md), Draft v0.3.

Marque um item somente quando houver evidência verificável: teste automatizado, vetor de teste, relatório, artefato gerado ou validação manual registrada.

## 0. Decisões aprovadas

### Bloqueiam a Fase 0

- [x] **DEC-001 — Nome:** “Chitãozinho”; identificadores `chitaozinho` e `CHITAOZINHO`.
- [x] **DEC-002 — Licença:** Apache-2.0 para verificador, schemas, extensão e backend.
- [x] **DEC-003 — Assinatura do servidor:** Ed25519.
- [x] **DEC-004 — Criptografia no navegador:** Web Crypto nativa; uma biblioteca consolidada é permitida somente para hash incremental ou fallback necessário.
- [x] **DEC-005 — Contêiner:** ZIP com ZIP64 automático quando necessário.
- [x] **DEC-006 — Versão inicial:** `protocol_version: 0.1.0` e `schema_version: 0.1.0`.
- [x] **DEC-007 — UI da extensão:** React, TypeScript e Vite.

### Bloqueiam a POC funcional exposta à internet

- [x] **DEC-008 — Autenticação mínima:** identidade local no desenvolvimento; magic link por e-mail antes de qualquer exposição pública.
- [x] **DEC-009 — Distribuição da extensão:** instalação unpacked na POC; pacote reproduzível e Chrome Web Store em etapa posterior.
- [x] **DEC-010 — Identidade do build:** versão, commit e hash do pacote registrados no manifesto.
- [x] **DEC-011 — Permissões:** `chrome.debugger` não será usado na POC.
- [x] **DEC-012 — Capturas parciais:** canvas e WebGL cobertos visualmente; iframes em best-effort; DRM e conteúdo protegido marcados como indisponíveis.

### Bloqueiam a POC probatória

- [x] **DEC-013 — TSA:** a POC pode usar uma TSA RFC 3161 confiável; o gate para comparar opções brasileiras antes de produção está em [`docs/tsa-evaluation.md`](docs/tsa-evaluation.md).
- [x] **DEC-014 — Trust store:** raízes TSA explícitas e versionadas; atualizações do trust store devem ser assinadas.
- [x] **DEC-015 — Storage:** Garage local e Ceph RGW Squid `19.2.5`
  self-hosted com Object Lock, imagem fixada por digest e OpenBao/Vault como
  backend SSE-KMS.
- [x] **DEC-016 — Retenção:** mínimo aceito no teste, 90 dias no gratuito, 5 anos no individual e prazo configurável no institucional.
- [x] **DEC-017 — Chave raiz:** gerada e mantida offline; chaves operacionais
  de staging/produção são Ed25519 não exportáveis no OpenBao Transit.
- [x] **DEC-018 — Rotação e revogação:** rotação operacional a cada 90 dias e lista de revogação assinada.
- [x] **DEC-019 — OpenTimestamps:** calendários públicos; agregação a cada hora ou 100 sessões, o que ocorrer primeiro.

### Bloqueiam produção

- [x] **DEC-020 — LGPD:** POC limitada a conteúdo público ou sintético; definição jurídica formal é gate obrigatório de produção.
- [x] **DEC-021 — Dados sensíveis:** dados reais de crianças, saúde e finanças ficam proibidos até política e revisão jurídica específicas.
- [x] **DEC-022 — Legal hold:** não será ativado antes de responsáveis, autorização, auditoria e liberação serem revisados juridicamente.
- [x] **DEC-023 — Transparência:** formato, schemas, verificador, código dos componentes e histórico de chaves serão públicos; auditorias serão publicadas quando disponíveis.
- [x] **DEC-024 — Railway:** staging primeiro; produção somente após POC
  probatória, revisão de segurança e autorização explícita; evidências
  permanecem no Ceph RGW externo.

## 1. Fundação do repositório

- [x] Repositório Git inicializado.
- [x] Branch principal e política de branches definidas.
- [x] Commits convencionais e atômicos adotados.
- [x] Estrutura `apps/`, `packages/`, `infra/`, `docs/` e `test-vectors/` criada.
- [x] `flake.nix` e `flake.lock` fornecem todas as ferramentas via `nix develop`.
- [x] Python gerenciado com `uv`, sem uso direto de `pip`.
- [x] Comandos únicos para format, lint, typecheck, test e build documentados.
- [x] `.gitignore`, `.env.example`, `README.md` e licença adicionados.
- [x] Secrets e dados capturados excluídos do repositório.
- [ ] CI executa verificações de TypeScript, Python e Rust.
- [x] Dependências possuem versões fixadas e política de atualização.
- [x] Changelog e versionamento dos builds definidos.

## 2. Fase 0 — Contrato probatório

### Schemas e protocolo

- [x] Schema de entrada da cadeia definido.
- [x] Schema de recibo definido.
- [x] Schema de `capture_close` definido.
- [x] Schema de `capture-manifest.json` definido.
- [x] Schema de `attestation.json` definido.
- [x] Schema de `package-index.json` definido.
- [x] Regras de compatibilidade e migração de schemas documentadas.
- [x] RFC 8785/JCS implementado de forma equivalente nas três linguagens.
- [x] Base64URL, hexadecimal, RFC 3339 e tempo monotônico normalizados.
- [x] Prefixos de domínio de todas as assinaturas documentados.
- [x] Sequência global, entrada gênese e mudança de `client_clock_id` implementadas.
- [x] `part_hash`, `artifact_hash`, `entry_hash`, `receipt_hash` e `session_root` implementados conforme a SPEC.

### Vetores de teste

- [x] Vetores válidos incluem JSON, bytes canônicos, hashes, chaves e assinaturas.
- [x] Vetores inválidos cobrem alteração de campo, encoding, ordem, assinatura e domínio.
- [x] TypeScript produz exatamente os resultados esperados.
- [x] Python produz exatamente os resultados esperados.
- [x] Rust produz exatamente os resultados esperados.
- [x] CI impede mudança incompatível não versionada.

### Empacotador e verificador

- [x] Empacotador preserva os arquivos originais.
- [x] `package-index.json` cobre todos os membros aplicáveis.
- [x] Assinaturas do cliente, servidor e índice são incluídas corretamente.
- [x] Hash externo do ZIP é gerado sem autorreferência.
- [x] CLI verifica pacote sem backend e sem autenticação.
- [x] CLI recalcula todos os hashes e cadeias.
- [x] CLI informa erro localizado e código de saída não zero.
- [x] Relatório diferencia integridade, completude e prova temporal.
- [x] Verificador rejeita path traversal, links simbólicos e nomes duplicados.
- [x] Verificador limita quantidade, tamanho, expansão, profundidade e memória.
- [x] Verificador rejeita schema e algoritmo desconhecidos de forma segura.

## 3. Fase 1 — POC funcional

### Extensão Chromium

- [x] Manifest V3 válido e instalável.
- [x] Usuário recebe explicação e registra consentimento antes da captura.
- [x] Captura de uma aba por pelo menos 60 segundos.
- [x] Vídeo WebM preservado sem recompressão.
- [x] Screenshot por viewport.
- [x] URL, título, user agent, resolução, viewport e timezone registrados como `client_reported`.
- [x] HTML/DOM e texto visível coletados quando permitidos.
- [x] Navegação, rolagem, screenshots adicionais e marcadores geram eventos.
- [x] Cada artefato registra método, procedência, permissões, intervalo e completude.
- [x] Artefatos indisponíveis ou parciais registram motivo explícito.
- [x] Hash e upload de vídeo são incrementais.
- [x] IndexedDB preserva buffer, partes, recibos e estado local.
- [x] Reinício da extensão cria novo `client_clock_id` e evento `clock_restarted`.
- [x] Indicadores de gravação, duração, upload, conexão e erros são visíveis.
- [x] `capture_close` é calculado e assinado antes de destruir a chave efêmera.

### API e persistência

- [x] Criar sessão e desafio do servidor.
- [x] Registrar chave pública efêmera.
- [x] Receber eventos com sequência e idempotência.
- [x] Receber partes com tamanho e `part_hash`.
- [x] Recalcular hash a partir dos bytes recebidos.
- [x] Persistir parte antes de emitir recibo.
- [x] Reenvio idêntico retorna o mesmo resultado lógico.
- [x] Reenvio divergente retorna conflito e registra incidente.
- [x] Finalizar artefato recalculando o hash completo.
- [x] Finalizar sessão apenas sem lacunas não declaradas.
- [x] Validar assinatura de `capture_close`.
- [x] Gerar e assinar manifesto de captura imutável.
- [x] Gerar pacote e hash externo.
- [x] Disponibilizar pacote sem permitir enumeração de sessões.
- [x] Eventos de auditoria são append-only e encadeados.
- [x] PostgreSQL é a fonte persistente de metadados e jobs.
- [x] Garage preserva bytes e versões no ambiente local.

### Experiência e relatório

- [x] Tela inicial oferece nova captura, capturas existentes, verificação e configurações.
- [x] Antes da captura, interface mostra dados coletados, limites e riscos.
- [x] Após a captura, interface mostra integridade, completude e estados independentes.
- [x] Download inclui pacote, hash externo e chaves públicas necessárias.
- [x] Relatório HTML apresenta resultados `íntegro`, `íntegro, mas incompleto`, `inválido` ou `não verificável`.
- [x] Relatório nunca afirma autoria, veracidade ou validade jurídica definitiva.
- [x] Interface preparada para pt-BR e inglês.
- [ ] Fluxo principal atende WCAG 2.2 AA.

### Validador web, metodologia e administração

- [x] Mesmo build do validador funciona pelo link público e offline.
- [x] ZIP principal, checksum e complemento são processados somente no
  navegador, sem upload ou telemetria dos arquivos.
- [x] Resultado detalha integridade, completude, confiança e prova temporal.
- [x] Relatórios HTML e JSON podem ser exportados.
- [x] Pacotes hostis respeitam limites e falham de forma localizada no navegador.
- [x] Metodologia pública explica captura, hashes, assinaturas, recibos, fontes
  de tempo, retenção e limitações.
- [x] `README.txt`, metodologia e guia de verificação acompanham o pacote.
- [x] Índice assinado cobre todos os documentos metodológicos.
- [ ] Administrador autenticado lista sessões e estados de forma paginada.
- [ ] Administrador pode baixar pacote, checksum e complemento.
- [ ] Imagens, vídeos, metadados e DOM possuem visualização segura.
- [ ] Visualizações e downloads administrativos geram eventos de auditoria.
- [ ] Usuários comuns não acessam rotas administrativas.
- [ ] API e interface administrativas não oferecem edição ou exclusão.

### Gate da POC funcional

- [x] Captura real de 60 segundos gera vídeo, screenshot e metadados.
- [x] Queda e retomada de upload não duplicam partes ou recibos.
- [x] Pacote é baixado e verificado integralmente offline.
- [x] Alteração de um byte é detectada e localizada.
- [x] Remoção, duplicação e reordenação de evento são detectadas.
- [x] Captura incompleta permanece verificável e claramente identificada.
- [x] Relatório HTML é gerado.
- [x] Vetores passam em TypeScript, Python e Rust.

## 4. Fase 2 — POC probatória completa

### RFC 3161

- [x] Requisição usa o hash do manifesto assinado.
- [x] `.tsq`, `.tsr`, certificado, cadeia e política são preservados.
- [x] `genTime`, cadeia, validade e revogação são verificados.
- [x] Falha da TSA muda apenas `timestamp_status`.
- [x] Retry usa exatamente o mesmo hash e registra cada tentativa.
- [x] Attestation referencia o manifesto sem modificá-lo.

### Merkle e OpenTimestamps

- [x] Sessões são agregadas sem publicar identificadores reversíveis.
- [x] Prova individual de inclusão Merkle é gerada.
- [x] Apenas a raiz agregada é submetida.
- [x] Prova `.ots` inicial é preservada.
- [x] Confirmação posterior gera novo complemento append-only.
- [x] Verificador distingue pendente, confirmado e inválido.

### Object Lock

- [ ] Bucket de teste possui versionamento e Object Lock desde a criação.
- [x] Testes usam somente conteúdo sintético ou público.
- [ ] Prazo de retenção de teste é mínimo e explícito.
- [ ] Sobrescrita e exclusão antecipada são recusadas.
- [ ] Manifestos, assinaturas, recibos, provas e relatórios são protegidos.
- [x] Falha de retenção não é apresentada como sucesso.

### Gate da POC probatória

- [x] Timestamp RFC 3161 válido.
- [x] Attestation válida sem alteração do manifesto.
- [x] Prova OpenTimestamps gerada.
- [x] Complemento atualizado e assinado.
- [ ] Cópia de teste bloqueada em Object Lock.
- [x] CLI valida timestamp, Merkle, OpenTimestamps e cadeia de attestations.
- [x] Pacote funcional continua verificável sem TSA, OpenTimestamps ou backend.

## 5. Segurança, privacidade e robustez

- [x] TLS obrigatório fora do desenvolvimento local.
- [x] Criptografia em repouso habilitada.
- [x] Chaves e secrets nunca aparecem em código ou logs.
- [x] Logs não incluem conteúdo, URL completa, tokens ou dados pessoais por padrão.
- [x] Telemetria é mínima e separada do conteúdo.
- [x] Backend indisponível não apaga o buffer local.
- [x] Downloads usam autorização e URLs expiráveis.
- [x] Sessões não podem ser enumeradas.
- [x] Limites de tamanho, duração, partes e taxa estão definidos.
- [x] Uso de CPU, memória e disco é medido durante captura.
- [x] A captura não degrada significativamente a página observada.
- [x] Falhas de disco, rede, storage e processo possuem recuperação documentada.
- [x] Ameaças e limitações aparecem na interface e no relatório.
- [x] Nenhum dado pessoal é publicado em blockchain.

## 6. Matriz mínima de testes

### Integridade e assinaturas

- [x] Alterar um byte do vídeo.
- [x] Substituir screenshot.
- [x] Alterar manifesto.
- [x] Remover, inserir, duplicar e reordenar entrada.
- [x] Usar chave, assinatura, algoritmo, `key_id` e domínio incorretos.

### Rede e recuperação

- [x] Queda e retomada de conexão.
- [x] Duplicação e retry idempotente.
- [x] Mesma sequência com bytes divergentes.
- [x] Encerramento com partes ausentes.
- [x] Reinício do cliente com buffer local.
- [x] Reinício do servidor durante finalização.

### Tempo e provas externas

- [x] Relógio do cliente incorreto.
- [x] Reinício do relógio monotônico.
- [x] TSA indisponível ou não confiável.
- [x] Certificado fora da validade no `genTime`.
- [x] Hash ou cadeia RFC 3161 divergente.
- [x] Merkle proof, raiz ou `.ots` inválidos.
- [x] Confirmação blockchain pendente.

### Pacotes hostis e storage

- [x] Path traversal, caminho absoluto e link simbólico.
- [x] Nome duplicado e arquivo obrigatório ausente.
- [x] ZIP bomb e JSON excessivamente profundo.
- [x] Schema ou algoritmo desconhecido.
- [x] Sobrescrita, exclusão antecipada e versionamento do storage.

### Captura e completude

- [x] Artefato indisponível.
- [x] Captura parcial de iframe, canvas, WebGL, DRM ou conteúdo protegido.
- [x] Queda durante gravação.
- [x] Navegação durante captura.
- [x] Página longa ou dinâmica.

## 7. Produção

- [x] API e workers empacotados em imagens OCI reproduzíveis.
- [x] Serviços publicados no Railway somente após autorização explícita.
- [x] Ambientes de staging e produção são separados.
- [ ] PostgreSQL possui backups e restauração testada.
- [x] Migrações possuem validação e rollback.
- [ ] Ceph RGW externo ao Railway com Object Lock é usado para evidências.
- [x] Volumes do Railway não são usados como storage probatório.
- [ ] Chave operacional de produção está provisionada como não exportável no
  OpenBao Transit, com versão e certificado correspondentes.
- [ ] Health checks, métricas, alertas e logs estruturados configurados.
  - [x] `/healthz` e `/readyz` separam vida e prontidão das dependências.
  - [x] `/metrics` autenticado expõe tráfego e saúde agregada dos jobs sem identificadores sensíveis.
  - [x] Logs da API e do worker são estruturados e usam somente metadados seguros.
  - [ ] Monitor externo e alertas estão conectados aos ambientes publicados.
- [x] Jobs são idempotentes e recuperáveis.
- [x] Runbooks cobrem TSA, OpenTimestamps, storage, banco e rotação de chaves.
- [x] SBOM e assinatura de builds são gerados por release.
- [ ] Política de retenção e exclusão foi revisada juridicamente.
- [x] Teste de restauração e rollback foi concluído.
- [ ] Revisão de segurança foi concluída.

## 8. Rastreabilidade dos requisitos

### Requisitos funcionais

- [x] RF-001 — iniciar sessão pela extensão.
- [x] RF-002 — registrar consentimento.
- [x] RF-003 — calcular SHA-256 no cliente.
- [x] RF-004 — encadear eventos.
- [x] RF-005 — emitir recibos assinados.
- [x] RF-006 — detectar lacunas, duplicações e reordenações.
- [x] RF-007 — preservar originais.
- [x] RF-008 — vincular `capture_close` e manifesto assinado.
- [x] RF-009 — solicitar timestamp RFC 3161.
- [x] RF-010 — gerar prova Merkle.
- [x] RF-011 — ancorar via OpenTimestamps.
- [x] RF-012 — armazenar artefatos finais em WORM.
- [x] RF-013 — gerar ZIP autocontido.
- [x] RF-014 — recalcular hashes localmente.
- [x] RF-015 — verificar offline e sem autenticação.
- [x] RF-016 — diferenciar integridade, tempo e autenticidade material.
- [x] RF-017 — registrar versões exatas dos componentes.
- [x] RF-018 — representar captura incompleta.
- [x] RF-019 — disponibilizar pacote e chaves.
- [x] RF-020 — preservar chaves históricas e rotação.
- [x] RF-021 — registrar método, procedência e completude.
- [x] RF-022 — garantir idempotência e detectar divergência.
- [x] RF-023 — manter estados independentes.
- [x] RF-024 — gerar attestations append-only.
- [x] RF-025 — limitar recursos e rejeitar pacotes inseguros.
- [x] RF-026 — validar no mesmo build web online/offline sem upload.
- [ ] RF-027 — administrar evidências de forma autenticada e somente leitura.
- [x] RF-028 — publicar e incorporar metodologia versionada ao pacote.

### Requisitos não funcionais

- [ ] RNF-001 — usar TLS moderno.
- [x] RNF-002 — respeitar finalidade e consentimento de uso dos dados.
- [x] RNF-003 — preservar buffer durante indisponibilidade.
- [x] RNF-004 — manter build identificável, changelog e logs seguros.
- [x] RNF-005 — verificar fora da plataforma.
- [x] RNF-006 — respeitar limites de desempenho e memória.
- [x] RNF-007 — suportar multipart e processamento assíncrono.
- [ ] RNF-008 — atender WCAG 2.2 AA.
- [x] RNF-009 — preparar pt-BR e inglês.
- [x] RNF-010 — oferecer build reproduzível do verificador.

## 9. Definição final de pronto

- [x] Testes relevantes passam.
- [x] Lint, typecheck e build passam.
- [x] Documentação acompanha o comportamento implementado.
- [x] Logs e falhas são auditáveis sem expor conteúdo sensível.
- [x] Originais nunca são alterados.
- [x] Limitações são informadas ao usuário.
- [x] Artefatos são verificáveis pela CLI.
- [x] Compatibilidade de schema foi preservada ou versionada.
- [x] Vetores compartilhados passam.
- [x] Diff foi revisado.
- [x] Mudanças foram divididas em commits atômicos.
- [x] Riscos e itens não validados foram registrados.
