# Metodologia Chitãozinho v0.1

## Escopo

O pacote registra bytes observados por uma extensão de navegador, sua sequência
de coleta e as provas técnicas produzidas a partir deles. Ele não comprova
autoria, veracidade material, identidade civil ou validade jurídica definitiva.

## Captura e integridade

A extensão coleta vídeo, screenshots, DOM e metadados quando permitido. Cada
parte recebe SHA-256 antes do upload. Eventos formam uma cadeia: cada entrada
inclui o hash da anterior e é assinada pela chave efêmera da sessão. Remoção,
alteração, duplicação e reordenação tornam a cadeia inválida.

O servidor recalcula os hashes dos bytes recebidos e emite recibos assinados
somente depois da persistência. O cliente assina `capture_close`; o servidor
valida a sequência, produz o manifesto imutável e o assina. O índice assinado
do pacote cobre todos os seus membros, inclusive esta metodologia.

## Fontes de tempo

- Horários do cliente são declarados pelo dispositivo e podem estar incorretos.
- Horários dos recibos são declarados e assinados pelo servidor.
- Um carimbo RFC 3161 externo demonstra que o hash do manifesto já existia até
  o `genTime` validado.
- OpenTimestamps ancora uma raiz Merkle no Bitcoin e demonstra existência até
  o bloco confirmado.

Provas temporais não demonstram que a captura ocorreu exatamente no instante
indicado. Quando geradas após o pacote principal, são distribuídas em um
complemento append-only sem modificar este ZIP.

## Preservação

Em ambientes probatórios, originais e provas finais são copiados para Ceph RGW
com versionamento, criptografia e Object Lock em modo `COMPLIANCE`. O estado
`locked` só pode ser apresentado depois da confirmação da retenção. Object Lock
protege contra alteração e exclusão antecipada; não substitui hashes,
assinaturas ou provas temporais.

## Verificação independente

O verificador recalcula hashes, valida índices, cadeia de eventos, recibos,
assinaturas, completude e, quando fornecidas, provas RFC 3161, Merkle e
OpenTimestamps. O verificador web usa o mesmo build online e offline e processa
os arquivos localmente no navegador.

A chave raiz ou seu fingerprint deve ser obtido por um canal independente. Uma
chave entregue apenas pelo mesmo servidor do pacote estabelece confiança
customizada, não confiança independente.

## Resultados

- `íntegro`: estrutura e provas fornecidas são válidas.
- `íntegro, mas incompleto`: os itens presentes são válidos, com ausências
  explicitamente declaradas.
- `inválido`: uma verificação obrigatória falhou.
- `não verificável`: faltam dados ou algoritmos necessários.

Integridade técnica não equivale a validação jurídica. O contexto, a legalidade
da obtenção e o peso probatório dependem de análise humana.
