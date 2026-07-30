# ACEITE.md

Checklist de implementação e aceite da [SPEC.md](SPEC.md), Draft v0.2.

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

- [x] **DEC-013 — TSA:** a POC pode usar uma TSA RFC 3161 confiável; opções brasileiras serão comparadas antes de produção.
- [x] **DEC-014 — Trust store:** raízes TSA explícitas e versionadas; atualizações do trust store devem ser assinadas.
- [x] **DEC-015 — Storage:** Garage local e AWS S3 com Object Lock em `sa-east-1`. MinIO foi descartado porque o pacote disponível está abandonado e possui vulnerabilidades críticas conhecidas.
- [x] **DEC-016 — Retenção:** mínimo aceito no teste, 90 dias no gratuito, 5 anos no individual e prazo configurável no institucional.
- [x] **DEC-017 — Chave raiz:** gerada e mantida offline; chaves operacionais de produção protegidas por KMS/HSM.
- [x] **DEC-018 — Rotação e revogação:** rotação operacional a cada 90 dias e lista de revogação assinada.
- [x] **DEC-019 — OpenTimestamps:** calendários públicos; agregação a cada hora ou 100 sessões, o que ocorrer primeiro.

### Bloqueiam produção

- [x] **DEC-020 — LGPD:** POC limitada a conteúdo público ou sintético; definição jurídica formal é gate obrigatório de produção.
- [x] **DEC-021 — Dados sensíveis:** dados reais de crianças, saúde e finanças ficam proibidos até política e revisão jurídica específicas.
- [x] **DEC-022 — Legal hold:** não será ativado antes de responsáveis, autorização, auditoria e liberação serem revisados juridicamente.
- [x] **DEC-023 — Transparência:** formato, schemas, verificador, código dos componentes e histórico de chaves serão públicos; auditorias serão publicadas quando disponíveis.
- [x] **DEC-024 — Railway:** staging primeiro; produção somente após POC probatória, revisão de segurança e autorização explícita; evidências permanecem no S3 externo.

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
- [ ] Base64URL, hexadecimal, RFC 3339 e tempo monotônico normalizados.
- [x] Prefixos de domínio de todas as assinaturas documentados.
- [ ] Sequência global, entrada gênese e mudança de `client_clock_id` implementadas.
- [x] `part_hash`, `artifact_hash`, `entry_hash`, `receipt_hash` e `session_root` implementados conforme a SPEC.

### Vetores de teste

- [x] Vetores válidos incluem JSON, bytes canônicos, hashes, chaves e assinaturas.
- [x] Vetores inválidos cobrem alteração de campo, encoding, ordem, assinatura e domínio.
- [x] TypeScript produz exatamente os resultados esperados.
- [x] Python produz exatamente os resultados esperados.
- [x] Rust produz exatamente os resultados esperados.
- [ ] CI impede mudança incompatível não versionada.

### Empacotador e verificador

- [x] Empacotador preserva os arquivos originais.
- [x] `package-index.json` cobre todos os membros aplicáveis.
- [x] Assinaturas do cliente, servidor e índice são incluídas corretamente.
- [x] Hash externo do ZIP é gerado sem autorreferência.
- [x] CLI verifica pacote sem backend e sem autenticação.
- [x] CLI recalcula todos os hashes e cadeias.
- [x] CLI informa erro localizado e código de saída não zero.
- [ ] Relatório diferencia integridade, completude e prova temporal.
- [x] Verificador rejeita path traversal, links simbólicos e nomes duplicados.
- [x] Verificador limita quantidade, tamanho, expansão, profundidade e memória.
- [x] Verificador rejeita schema e algoritmo desconhecidos de forma segura.

## 3. Fase 1 — POC funcional

### Extensão Chromium

- [ ] Manifest V3 válido e instalável.
- [ ] Usuário recebe explicação e registra consentimento antes da captura.
- [ ] Captura de uma aba por pelo menos 60 segundos.
- [ ] Vídeo WebM preservado sem recompressão.
- [ ] Screenshot por viewport.
- [ ] URL, título, user agent, resolução, viewport e timezone registrados como `client_reported`.
- [ ] HTML/DOM e texto visível coletados quando permitidos.
- [ ] Navegação, rolagem, screenshots adicionais e marcadores geram eventos.
- [ ] Cada artefato registra método, procedência, permissões, intervalo e completude.
- [ ] Artefatos indisponíveis ou parciais registram motivo explícito.
- [ ] Hash e upload de vídeo são incrementais.
- [ ] IndexedDB preserva buffer, partes, recibos e estado local.
- [ ] Reinício da extensão cria novo `client_clock_id` e evento `clock_restarted`.
- [ ] Indicadores de gravação, duração, upload, conexão e erros são visíveis.
- [ ] `capture_close` é calculado e assinado antes de destruir a chave efêmera.

### API e persistência

- [ ] Criar sessão e desafio do servidor.
- [ ] Registrar chave pública efêmera.
- [ ] Receber eventos com sequência e idempotência.
- [ ] Receber partes com tamanho e `part_hash`.
- [ ] Recalcular hash a partir dos bytes recebidos.
- [ ] Persistir parte antes de emitir recibo.
- [ ] Reenvio idêntico retorna o mesmo resultado lógico.
- [ ] Reenvio divergente retorna conflito e registra incidente.
- [ ] Finalizar artefato recalculando o hash completo.
- [ ] Finalizar sessão apenas sem lacunas não declaradas.
- [ ] Validar assinatura de `capture_close`.
- [ ] Gerar e assinar manifesto de captura imutável.
- [ ] Gerar pacote e hash externo.
- [ ] Disponibilizar pacote sem permitir enumeração de sessões.
- [ ] Eventos de auditoria são append-only e encadeados.
- [ ] PostgreSQL é a fonte persistente de metadados e jobs.
- [ ] Garage preserva bytes e versões no ambiente local.

### Experiência e relatório

- [ ] Tela inicial oferece nova captura, capturas existentes, verificação e configurações.
- [ ] Antes da captura, interface mostra dados coletados, limites e riscos.
- [ ] Após a captura, interface mostra integridade, completude e estados independentes.
- [ ] Download inclui pacote, hash externo e chaves públicas necessárias.
- [ ] Relatório HTML apresenta resultados `íntegro`, `íntegro, mas incompleto`, `inválido` ou `não verificável`.
- [ ] Relatório nunca afirma autoria, veracidade ou validade jurídica definitiva.
- [ ] Interface preparada para pt-BR e inglês.
- [ ] Fluxo principal atende WCAG 2.2 AA.

### Gate da POC funcional

- [ ] Captura real de 60 segundos gera vídeo, screenshot e metadados.
- [ ] Queda e retomada de upload não duplicam partes ou recibos.
- [ ] Pacote é baixado e verificado integralmente offline.
- [ ] Alteração de um byte é detectada e localizada.
- [ ] Remoção, duplicação e reordenação de evento são detectadas.
- [ ] Captura incompleta permanece verificável e claramente identificada.
- [ ] Relatório HTML é gerado.
- [ ] Vetores passam em TypeScript, Python e Rust.

## 4. Fase 2 — POC probatória completa

### RFC 3161

- [ ] Requisição usa o hash do manifesto assinado.
- [ ] `.tsq`, `.tsr`, certificado, cadeia e política são preservados.
- [ ] `genTime`, cadeia, validade e revogação são verificados.
- [ ] Falha da TSA muda apenas `timestamp_status`.
- [ ] Retry usa exatamente o mesmo hash e registra cada tentativa.
- [ ] Attestation referencia o manifesto sem modificá-lo.

### Merkle e OpenTimestamps

- [ ] Sessões são agregadas sem publicar identificadores reversíveis.
- [ ] Prova individual de inclusão Merkle é gerada.
- [ ] Apenas a raiz agregada é submetida.
- [ ] Prova `.ots` inicial é preservada.
- [ ] Confirmação posterior gera novo complemento append-only.
- [ ] Verificador distingue pendente, confirmado e inválido.

### Object Lock

- [ ] Bucket de teste possui versionamento e Object Lock desde a criação.
- [ ] Testes usam somente conteúdo sintético ou público.
- [ ] Prazo de retenção de teste é mínimo e explícito.
- [ ] Sobrescrita e exclusão antecipada são recusadas.
- [ ] Manifestos, assinaturas, recibos, provas e relatórios são protegidos.
- [ ] Falha de retenção não é apresentada como sucesso.

### Gate da POC probatória

- [ ] Timestamp RFC 3161 válido.
- [ ] Attestation válida sem alteração do manifesto.
- [ ] Prova OpenTimestamps gerada.
- [ ] Complemento atualizado e assinado.
- [ ] Cópia de teste bloqueada em Object Lock.
- [ ] CLI valida timestamp, Merkle, OpenTimestamps e cadeia de attestations.
- [ ] Pacote funcional continua verificável sem TSA, OpenTimestamps ou backend.

## 5. Segurança, privacidade e robustez

- [ ] TLS obrigatório fora do desenvolvimento local.
- [ ] Criptografia em repouso habilitada.
- [ ] Chaves e secrets nunca aparecem em código ou logs.
- [ ] Logs não incluem conteúdo, URL completa, tokens ou dados pessoais por padrão.
- [ ] Telemetria é mínima e separada do conteúdo.
- [ ] Backend indisponível não apaga o buffer local.
- [ ] Downloads usam autorização e URLs expiráveis.
- [ ] Sessões não podem ser enumeradas.
- [ ] Limites de tamanho, duração, partes e taxa estão definidos.
- [ ] Uso de CPU, memória e disco é medido durante captura.
- [ ] A captura não degrada significativamente a página observada.
- [ ] Falhas de disco, rede, storage e processo possuem recuperação documentada.
- [ ] Ameaças e limitações aparecem na interface e no relatório.
- [ ] Nenhum dado pessoal é publicado em blockchain.

## 6. Matriz mínima de testes

### Integridade e assinaturas

- [ ] Alterar um byte do vídeo.
- [ ] Substituir screenshot.
- [ ] Alterar manifesto.
- [ ] Remover, inserir, duplicar e reordenar entrada.
- [ ] Usar chave, assinatura, algoritmo, `key_id` e domínio incorretos.

### Rede e recuperação

- [ ] Queda e retomada de conexão.
- [ ] Duplicação e retry idempotente.
- [ ] Mesma sequência com bytes divergentes.
- [ ] Encerramento com partes ausentes.
- [ ] Reinício do cliente com buffer local.
- [ ] Reinício do servidor durante finalização.

### Tempo e provas externas

- [ ] Relógio do cliente incorreto.
- [ ] Reinício do relógio monotônico.
- [ ] TSA indisponível ou não confiável.
- [ ] Certificado fora da validade no `genTime`.
- [ ] Hash ou cadeia RFC 3161 divergente.
- [ ] Merkle proof, raiz ou `.ots` inválidos.
- [ ] Confirmação blockchain pendente.

### Pacotes hostis e storage

- [ ] Path traversal, caminho absoluto e link simbólico.
- [ ] Nome duplicado e arquivo obrigatório ausente.
- [ ] ZIP bomb e JSON excessivamente profundo.
- [ ] Schema ou algoritmo desconhecido.
- [ ] Sobrescrita, exclusão antecipada e versionamento do storage.

### Captura e completude

- [ ] Artefato indisponível.
- [ ] Captura parcial de iframe, canvas, WebGL, DRM ou conteúdo protegido.
- [ ] Queda durante gravação.
- [ ] Navegação durante captura.
- [ ] Página longa ou dinâmica.

## 7. Produção

- [ ] API e workers empacotados em imagens OCI reproduzíveis.
- [ ] Serviços publicados no Railway somente após autorização explícita.
- [ ] Ambientes de staging e produção são separados.
- [ ] PostgreSQL possui backups e restauração testada.
- [ ] Migrações possuem validação e rollback.
- [ ] S3 externo com Object Lock é usado para evidências.
- [ ] Volumes do Railway não são usados como storage probatório.
- [ ] Chaves de produção ficam em KMS/HSM ou solução equivalente aprovada.
- [ ] Health checks, métricas, alertas e logs estruturados configurados.
- [ ] Jobs são idempotentes e recuperáveis.
- [ ] Runbooks cobrem TSA, OpenTimestamps, storage, banco e rotação de chaves.
- [ ] SBOM e assinatura de builds são gerados por release.
- [ ] Política de retenção e exclusão foi revisada juridicamente.
- [ ] Teste de restauração e rollback foi concluído.
- [ ] Revisão de segurança foi concluída.

## 8. Rastreabilidade dos requisitos

### Requisitos funcionais

- [ ] RF-001 — iniciar sessão pela extensão.
- [ ] RF-002 — registrar consentimento.
- [ ] RF-003 — calcular SHA-256 no cliente.
- [ ] RF-004 — encadear eventos.
- [ ] RF-005 — emitir recibos assinados.
- [ ] RF-006 — detectar lacunas, duplicações e reordenações.
- [ ] RF-007 — preservar originais.
- [ ] RF-008 — vincular `capture_close` e manifesto assinado.
- [ ] RF-009 — solicitar timestamp RFC 3161.
- [ ] RF-010 — gerar prova Merkle.
- [ ] RF-011 — ancorar via OpenTimestamps.
- [ ] RF-012 — armazenar artefatos finais em WORM.
- [ ] RF-013 — gerar ZIP autocontido.
- [ ] RF-014 — recalcular hashes localmente.
- [ ] RF-015 — verificar offline e sem autenticação.
- [ ] RF-016 — diferenciar integridade, tempo e autenticidade material.
- [ ] RF-017 — registrar versões exatas dos componentes.
- [ ] RF-018 — representar captura incompleta.
- [ ] RF-019 — disponibilizar pacote e chaves.
- [ ] RF-020 — preservar chaves históricas e rotação.
- [ ] RF-021 — registrar método, procedência e completude.
- [ ] RF-022 — garantir idempotência e detectar divergência.
- [ ] RF-023 — manter estados independentes.
- [ ] RF-024 — gerar attestations append-only.
- [ ] RF-025 — limitar recursos e rejeitar pacotes inseguros.

### Requisitos não funcionais

- [ ] RNF-001 — usar TLS moderno.
- [ ] RNF-002 — respeitar finalidade e consentimento de uso dos dados.
- [ ] RNF-003 — preservar buffer durante indisponibilidade.
- [ ] RNF-004 — manter build identificável, changelog e logs seguros.
- [ ] RNF-005 — verificar fora da plataforma.
- [ ] RNF-006 — respeitar limites de desempenho e memória.
- [ ] RNF-007 — suportar multipart e processamento assíncrono.
- [ ] RNF-008 — atender WCAG 2.2 AA.
- [ ] RNF-009 — preparar pt-BR e inglês.
- [ ] RNF-010 — oferecer build reproduzível do verificador.

## 9. Definição final de pronto

- [ ] Testes relevantes passam.
- [ ] Lint, typecheck e build passam.
- [ ] Documentação acompanha o comportamento implementado.
- [ ] Logs e falhas são auditáveis sem expor conteúdo sensível.
- [ ] Originais nunca são alterados.
- [ ] Limitações são informadas ao usuário.
- [ ] Artefatos são verificáveis pela CLI.
- [ ] Compatibilidade de schema foi preservada ou versionada.
- [ ] Vetores compartilhados passam.
- [ ] Diff foi revisado.
- [ ] Mudanças foram divididas em commits atômicos.
- [ ] Riscos e itens não validados foram registrados.
