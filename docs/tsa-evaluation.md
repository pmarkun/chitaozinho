# Avaliação de TSA brasileira

Este documento define o gate para escolher a Autoridade de Carimbo do Tempo
(ACT) antes da produção. Ele não seleciona nem contrata um fornecedor.

## Lista inicial

A lista deve ser refeita imediatamente antes da seleção usando o cadastro
oficial do ITI. Em 30 de julho de 2026, a
[página de ACTs credenciadas](https://www.gov.br/iti/pt-br/assuntos/icp-brasil/autoridades-de-carimbo-do-tempo),
atualizada em 7 de maio de 2025, relacionava:

| ACT | Interoperabilidade | SLA, preço e contrato |
| --- | --- | --- |
| CAIXA | confirmar com teste | confirmar com fornecedor |
| SERPRO | confirmar com teste | confirmar com fornecedor |
| CERTISIGN | confirmar com teste | confirmar com fornecedor |
| VALID | confirmar com teste | confirmar com fornecedor |
| BRY | confirmar com teste | confirmar com fornecedor |
| QUICKSOFT | confirmar com teste | confirmar com fornecedor |
| SAFEWEB | confirmar com teste | confirmar com fornecedor |
| SOLUTI | confirmar com teste | confirmar com fornecedor |
| PRODESP | confirmar com teste | confirmar com fornecedor |

O credenciamento é apenas o primeiro filtro. Nenhum endpoint, preço ou SLA deve
ser inferido dessa lista.

## Critérios eliminatórios

- endpoint RFC 3161 que aceite TSQ e devolva TSR para SHA-256;
- nonce, `genTime`, policy OID, certificado e cadeia verificáveis;
- cadeia, CRL ou OCSP disponíveis para o trust store versionado;
- TLS moderno, autenticação documentada e ambiente de teste;
- contrato compatível com LGPD, retenção de logs e resposta a incidentes;
- SLA, limites, suporte, portabilidade e custo formalmente informados.

A avaliação técnica segue o [RFC 3161](https://www.rfc-editor.org/rfc/rfc3161)
e os requisitos da
[Rede de Carimbo do Tempo da ICP-Brasil](https://www.gov.br/iti/pt-br/assuntos/legislacao/instrucoes-normativas/in2020_17_doc-icp-11-01.htm).

## Ensaio comparável

1. Solicitar endpoint, cadeia, política, documentação e proposta a cada ACT.
2. Enviar o mesmo hash SHA-256 sintético a todas as candidatas qualificadas.
3. Preservar TSQ, TSR, certificado, cadeia, política e resultado da validação.
4. Validar cada resposta com o verificador atual, sem trust implícito.
5. Medir latência, taxa de erro, retry idempotente e comportamento de falha.
6. Registrar matriz técnica, operacional, comercial, jurídica e de segurança.

Produção só pode avançar quando uma candidata passar no ensaio de
interoperabilidade, tiver trust store aprovado e contrato revisado. A POC
continua usando a TSA externa configurável; este gate não altera manifestos ou
provas existentes.
