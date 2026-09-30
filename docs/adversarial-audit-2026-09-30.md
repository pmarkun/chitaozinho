# Ensaio adversarial do pacote de evidências — 30/09/2026

Registro histórico da primeira rodada, anterior às correções. O estado atualizado
está na [segunda rodada](adversarial-audit-round2-2026-09-30.md).

## Conclusão

O ensaio confirmou cinco lacunas de validação/interpretação e uma limitação
deliberada de confiança. Não demonstrou falsificação de Ed25519 nem troca de
artefatos assinados por um atacante sem chaves. Não constitui certificação de
segurança ou parecer sobre admissibilidade jurídica.

Recomenda-se corrigir as inconsistências abaixo antes de apresentar o sistema
como tecnicamente endurecido. O material já pode apoiar uma auditoria externa,
desde que acompanhado dos achados e das limitações.

## Escopo e método

- Base: commit `35640c96db69e3b9afcde6507e390afebb904544`, versão 0.1.6.
- Branch local: `codex/adversarial-evidence-audit`.
- Alvo: formato do ZIP probatório, empacotador Rust e validadores Rust/TypeScript.
- Pacotes sintéticos gerados pelos testes, com chaves efêmeras de teste.
- Não foi recebido nem selecionado um ZIP probatório específico do usuário.
  Os ZIPs de distribuição da extensão presentes no checkout não são o alvo.
- Nenhuma chamada a produção, mudança de secrets ou alteração de artefato original.
- Alterações desta rodada: testes de caracterização e este relatório. As falhas
  permanecem abertas; nenhum comportamento de produção foi corrigido.

Separaram-se dois adversários: editor do ZIP sem chaves e produtor defeituoso ou
comprometido que consegue emitir documentos assinados. Um verificador independente
deve detectar inconsistências internas também no segundo caso; assinar uma
declaração não garante que ela seja coerente.

## Achados reproduzidos

| ID | Caso | Pré-condição | Web | CLI | Prioridade sugerida |
| --- | --- | --- | --- | --- | --- |
| A01 | Índice JSON com duas chaves `session_id` | Editar apenas o índice, sem reassinar | Aceita | Recusa | Média |
| A02 | `complete` com `known_gaps` não vazio | Produtor com assinatura do cliente e servidor | `integral` | `integral` | Alta |
| A03 | Arquivo de recibos vazio | Produtor com assinatura do índice | Aceita | Aceita e declara `remote_custody_receipts` | Alta |
| A04 | Recibo assinado nomeia outra sessão | Produtor com assinatura do recibo e índice | Aceita | Aceita | Média |
| A05 | Chave operacional explícita conflitante com certificado válido | Pacote certificado e configuração de confiança conflitante | Ignora a chave explícita | Modos simultâneos recusados pela CLI | Média |
| L01 | Pacote fabricado com chaves próprias | Gerar pacote próprio, sem chaves oficiais | `integral` com `self_declared` e aviso | Exige âncora explícita | Limitação deliberada |

### A01 — Ambiguidade no índice sem acesso às chaves

Após assinar o pacote válido, inserir `"session_id":"forged-first-value"` antes
do `session_id` original em `package-index.json`. O índice não é membro hasheado
de si próprio; a assinatura protege seu conteúdo interpretado e canonicalizado.
`JSON.parse` conserva o último valor, de modo que a assinatura continua válida.
O desserializador do índice Rust rejeita o campo repetido.

Impacto demonstrado: um mesmo ZIP ambíguo é aceito pela web e recusado pela CLI.
O valor efetivamente verificado pela web continua sendo o original. Não se
demonstrou alteração do identificador efetivo ou do conteúdo coberto pela assinatura.
Um consumidor que interprete a primeira ocorrência pode enxergar outra declaração.

Correção proposta: rejeitar chaves JSON repetidas antes de qualquer canonicalização,
com regra uniforme para JSON e JSONL nas linguagens. Incluir vetores compartilhados.

### A02 — Completude confiada ao manifesto

O encerramento assinado declara `known_gaps: ["Main DOM unavailable"]`, mas o
manifesto assinado permanece `status: "complete"`. Ambos os verificadores aceitam
o conjunto e retornam `integral`, em vez de detectar a inconsistência ou indicar
incompletude.

O fluxo normal da API calcula `incomplete` para lacunas conhecidas. O ataque
reproduzido depende de produtor defeituoso/comprometido ou de outro empacotador;
não demonstra que o endpoint normal permita essa contradição.

Correção proposta: conferir independentemente o vínculo entre estado, lacunas e
artefatos indisponíveis, sem confiar apenas no rótulo assinado pelo servidor.

### A03 — Validação vazia de custódia

Substituir os recibos por arquivo vazio antes de assinar o índice. A cadeia de
eventos e o encerramento continuam válidos. A CLI declara `receipt_chain` e
`remote_custody_receipts` válidos; a web apresenta zero recibos como verificação
válida e não identifica custódia só-hash pela ausência deles.

Correção proposta: exigir recibos necessários ao perfil e validar sua cobertura,
segundo a semântica de entradas/lotes. Ausência de prova de custódia deve ser
explicitada, nunca inferida como custódia remota. Testar remoção de prefixo,
sufixo e cadeia inteira, além de modos misturados.

### A04 — Sessão do recibo não conferida

Reassinar um recibo com `session_id: "foreign-session"`, mantendo o hash de entrada
da sessão atual. Os validadores conferem hash, assinatura e encadeamento, mas
não esse vínculo de sessão. O empacotador Rust também aceita o conjunto.

Correção proposta: comparar sessão e demais vínculos de identidade/artefato do
recibo com a entrada correspondente. Este teste não demonstra replay direto de
um recibo real de outra sessão: o hash de entrada inclui o identificador da sessão.

### A05 — Precedência silenciosa entre âncoras

Fornecer pacote certificado pela raiz de teste e uma chave operacional explícita
que não corresponde ao pacote. A web retorna `root_certified`: o ramo certificado
retorna antes da comparação da chave operacional. A raiz do ensaio é sintética;
não se demonstrou emissão de certificado pela raiz oficial.

Correção proposta: definir modos mutuamente exclusivos ou exigir coerência entre
as âncoras fornecidas. Uma restrição explícita não deve ser ignorada silenciosamente.

### L01 — Integridade autoconsistente não autentica origem

Um pacote inteiramente criado pelo atacante passa na web sem chave explícita,
com `result: integral`, `trustMode: self_declared` e aviso de confiança. Com chave
independente incompatível, a mesma entrada é recusada. O aviso existente é correto;
o risco está em interpretar o resultado agregado como emissão oficial.

Recomendação: para auditoria, registrar separadamente integridade, origem
autenticada, cobertura, custódia e prova temporal. Distribuir a raiz confiável por
canal independente do pacote. Não aceitar a chave embutida como autenticação
de origem.

## Resistências observadas

Os novos testes recusaram alterações posteriores à assinatura de artefato,
remoção de arquivo, inclusão de membro fora do índice, troca do identificador no
índice, assinatura inválida e registro de chaves inválido.

Os testes Rust existentes também passaram para alteração de manifesto/screenshot,
chave ou domínio incorreto, alteração/remoção/duplicação/reordenação de eventos,
traversal, membros ausentes/extras, expansão suspeita, JSON profundo, delegação
pela raiz e revogação. Isso demonstra resistência aos casos exercitados, não
ausência geral de vulnerabilidades.

## Reprodução e validação

```sh
nix develop --command cargo test --workspace
nix develop --command pnpm --filter @chitaozinho/verifier-web test
nix develop --command uv run pytest apps/api/tests/test_hash_only.py apps/api/tests/test_capture_flow.py apps/api/tests/test_key_management.py apps/api/tests/test_proof_failures.py packages/protocol-py/tests -q
```

Resultados: 25 testes Rust, 24 testes web e 34 testes Python passaram. Foram
adicionados 16 casos: 4 Rust e 12 web. Também passaram typecheck/lint web,
formatação dos arquivos alterados, Clippy e revisão de whitespace do diff.

`nix develop --command ./scripts/security-audit` também passou: OSV examinou os
três lockfiles e Trivy não reportou secrets ou configurações de risco alto/crítico
na árvore rastreada pelo Git, usando o cache de políticas disponível. Isso não
inspeciona o ambiente implantado nem inclui arquivos locais não rastreados.

**Os testes de caracterização dos achados passam quando a lacuna está presente.**
Servem para preservar a reprodução desta rodada; não são critérios de aceite de
segurança. Ao corrigir cada achado, alterar a expectativa para recusa ou classificação
correta e manter os casos negativos na CI.

## Limites e próxima rodada

Não se validaram interface em navegadores reais, implantação pública, configuração
real de OpenBao/storage, acesso administrativo, isolamento do dispositivo,
fuzzing prolongado, limites sob carga nem todo o gate `scripts/check`. Esta rodada
não é um pentest completo da arquitetura. O teste Python de `hash_only` confirmou
o fluxo com conteúdo sintético; não comprova autenticidade da página de origem.

Conteúdo fabricado antes de receber hashes continua podendo ser íntegro. No perfil
`hash_only`, o servidor registra declarações do cliente, sem observar os bytes.
Essa fronteira está documentada na especificação e exige apresentação explícita
na auditoria. Timestamp também não resolve autenticidade de conteúdo anterior ao
processamento.

Ordem proposta: corrigir A02/A03, unificar interpretação JSON (A01), validar vínculos
de recibos (A04), explicitar política de confiança (A05/L01), e então realizar um
ensaio independente com captura real e revisão operacional. A utilidade jurídica
deve ser apreciada pela equipe jurídica/pericial sobre essas garantias delimitadas.
