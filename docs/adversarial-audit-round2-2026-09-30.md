# Correções e segunda rodada adversarial — 30/09/2026

## Resultado

As cinco lacunas A01–A05 da [primeira rodada](adversarial-audit-2026-09-30.md)
foram corrigidas localmente. Os casos antes aceitos passaram a exigir recusa.
Na segunda rodada, duas variantes adicionais de A05 foram identificadas e
corrigidas: ignorar uma raiz explicitamente requerida e aceitar uma delegação
incompleta por fallback para confiança autodeclarada.

Não se demonstrou nova aceitação indevida nos casos executados após as correções.
Isso não equivale a certificação de segurança ou avaliação de admissibilidade
jurídica. Nenhum deploy, acesso a produção ou alteração de secrets foi realizado.

## Correções

| Caso | Comportamento corrigido |
| --- | --- |
| A01 | Leitura estrita de JSON/JSONL antes da canonicalização; chaves repetidas são recusadas em qualquer profundidade, incluindo nomes equivalentes por escape Unicode. |
| A02 | Manifesto `complete` com lacunas ou artefatos indisponíveis é recusado. Capturas explicitamente parciais continuam válidas como parciais. |
| A03 | Todas as entradas `artifact_part` exigem recibo. Remoção de prefixo, meio ou sufixo é detectada. Ausência de recibos sem partes não vira prova de custódia remota. |
| A04 | Recibos conferem sessão, hash da entrada, artefato, número e hash da parte; sequência duplicada ou fora de ordem e mistura de custódia são recusadas. |
| A05 | Chave operacional explícita é conferida também nos pacotes certificados. Uma raiz explícita exige delegação; certificado e revogações incompletos não permitem fallback. |

As proteções estão no empacotador/verificador Rust e no verificador web. A leitura
estrita também foi disponibilizada no protocolo Python e aplicada às declarações
de hash e entradas recebidas pelos headers de upload, inclusive em replay.
Não foi substituído o parser genérico do framework para todas as rotas da API.

Não foram adicionadas dependências. Os parsers foram exercitados por 18 vetores
compartilhados entre TypeScript, Rust e Python, além de limite de profundidade.
Não há mudança de versão do formato nem alteração dos bytes de pacotes existentes.
Pacotes ambíguos ou internamente inconsistentes antes tolerados passam a ser
recusados: isso é uma restrição intencional de validação.

## Segunda rodada

Foram exercitados novamente os cinco ataques originais, adulterações posteriores
à assinatura e casos corretamente assinados, porém contraditórios. A rodada
ampliada incluiu:

- recibos removidos no início, meio e final, duplicados ou reordenados;
- recibos com sessão, artefato, número ou hash de parte divergentes;
- mistura de `hash_registered` e custódia remota;
- JSON com nomes repetidos no índice e dentro de entradas JSONL;
- nomes equivalentes por escape, chave vazia e `__proto__` repetido;
- delegação incompleta e raiz explícita ignorada;
- controles positivos: confiança certificada e explícita coerentes, perfil só-hash,
  captura parcial e recibos válidos.

Os casos de recibos ampliados em Rust conferem diretamente a rotina de validação
com assinaturas recalculadas, para que erros de assinatura não mascarem erros
semânticos. As regressões principais também constroem ZIPs deliberadamente
inconsistentes fora do empacotador normal e os submetem ao verificador independente.

## Validação e reprodução

```sh
nix develop --command ./scripts/check
nix develop --command uv run python scripts/test-adversarial-packages.py --all-engines
nix develop --command ./scripts/security-audit
```

O novo ensaio de pacotes integra `scripts/check`: gera uma captura sintética usando
a API local em TestClient, produz uma cópia do ZIP com índice ambíguo, verifica
aceitação/recusa na CLI e exercita a página no Chromium. Os arquivos temporários
são isolados; nenhum original do usuário é modificado.

O modo `--all-engines` inclui Firefox e WebKit para o caso adversarial. A consulta
da prova temporal é simulada localmente. O service worker é desativado apenas nesse
caso para manter a consulta dentro do mock; o fluxo offline tem testes separados
na suíte principal.

Unidades: 27 testes Rust, 46 de protocolo TypeScript, 35 do verificador web,
37 da extensão e 140 Python passaram. Uma unidade da extensão e quatro testes
Python de integração real ficaram ignorados pelas condições do ambiente.

O gate `scripts/check` terminou com sucesso no estado final: também passaram
13 testes web de navegador, 8 da extensão e o ensaio de captura só-hash da extensão
instalada em Chromium. Os casos opt-in de pacote externo e um caso da extensão
ficaram ignorados. O scanner OSV/Trivy passou sobre a árvore rastreada, incluindo
os novos arquivos desta mudança; não reportou vulnerabilidades não aceitas,
secrets ou configurações de risco alto/crítico no escopo examinado.

Também foram verificados formatação, lint, tipos, builds, migrações em SQLite
temporário, reprodutibilidade da extensão e configurações de infraestrutura.
A matriz da página adversarial foi Chromium, Firefox e WebKit em Linux,
1440×900 e 360×800: pacote válido, advertência de origem autodeclarada, custódia
só-hash, troca pelo ZIP adulterado, recusa visível e remoção do resultado anterior.
Nenhum erro de página ou overflow horizontal ocorreu nesses testes isolados.

O Chrome DevTools conectado foi acessível, mas recusou a seleção dos arquivos por
sua configuração de diretórios permitidos. A interação com arquivos foi validada
pelo Playwright do projeto. WebKit em Linux não é Safari ou iPhone real.

## Limites remanescentes

A limitação L01 permanece explícita: um pacote autodeclarado pode ser íntegro
sem demonstrar emissão oficial. Integridade não prova que a página ou conteúdo
existia antes da coleta. O perfil `hash_only` não transfere ao servidor a guarda
ou observação dos bytes originais.

Não foram realizados pentest externo, fuzzing prolongado, revisão do ambiente
implantado, Object Lock real, testes com dados probatórios de terceiros, nem
validação em dispositivos reais, Safari/iOS ou Windows/Edge. PostgreSQL/Garage
reais ficaram fora desta rodada; os quatro testes correspondentes exigem execução
opt-in. A consulta externa de provas temporais não foi atestada por este ensaio.

O scanner é um complemento à revisão de código, não prova ausência de falhas.
O relatório histórico permanece preservado para permitir comparar antes e depois.
