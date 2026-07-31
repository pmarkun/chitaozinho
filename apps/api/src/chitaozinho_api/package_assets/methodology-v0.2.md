# Metodologia Chitãozinho v0.2

## O que o Chitãozinho atesta

O pacote vincula os bytes observados pela extensão à sequência da coleta e às
provas técnicas produzidas a partir deles. Sua validação confirma a integridade
dos arquivos, a continuidade da sessão, o vínculo entre artefatos e eventos e,
quando disponíveis, os marcos temporais externos.

## Captura contextual

A extensão registra vídeo da navegação, screenshots, estrutura DOM, texto
visível e metadados do navegador quando cada recurso está disponível. Todo
artefato declara seu método de coleta, procedência técnica e estado. Ausências
são preservadas no manifesto com o respectivo motivo, sem ocultar lacunas.

## Cadeia de integridade

Cada parte recebe SHA-256 antes do envio. Os eventos formam uma cadeia em que
cada entrada referencia o hash anterior e recebe a assinatura da chave efêmera
da sessão. Alteração, remoção, duplicação ou reordenação rompe essa cadeia e é
detectada pelo verificador.

O servidor recalcula os hashes dos bytes recebidos e emite recibos assinados
somente depois da persistência. No encerramento, o cliente assina
`capture_close`; o servidor valida a sequência, produz o manifesto imutável e o
assina. O índice assinado cobre todos os membros do ZIP, inclusive esta
metodologia.

## Provas de tempo

- Os eventos preservam os horários declarados pelo dispositivo.
- Os recibos acrescentam horários declarados e assinados pelo servidor.
- RFC 3161 demonstra que o hash do manifesto já existia até o `genTime`
  validado por uma autoridade externa.
- OpenTimestamps ancora uma raiz Merkle no Bitcoin e demonstra que o hash já
  existia até o bloco confirmado.

Provas concluídas depois do pacote principal são distribuídas em complemento
append-only. O ZIP original e seu hash permanecem inalterados.

## Preservação imutável

Em ambientes probatórios, originais e provas finais são copiados para Ceph RGW
com versionamento, criptografia e Object Lock em modo `COMPLIANCE`. O estado
`locked` só é apresentado depois da confirmação da retenção. Assim, hashes,
assinaturas, provas temporais e retenção atuam como camadas verificáveis e
complementares.

## Verificação independente

O verificador recalcula hashes e valida índice, cadeia de eventos, recibos,
assinaturas, completude e, quando fornecidas, provas RFC 3161, Merkle e
OpenTimestamps. O mesmo build funciona pelo link público ou offline e processa
os arquivos localmente no navegador.

Uma chave operacional obtida por canal independente permite confirmar também a
identidade operacional que assinou o pacote. Sem essa chave, a consistência das
assinaturas continua verificável contra a chave incorporada ao próprio pacote.

## Resultados

- `íntegro`: estrutura e provas fornecidas são válidas.
- `íntegro, mas incompleto`: os itens presentes são válidos e as ausências
  estão explicitamente declaradas.
- `inválido`: uma verificação obrigatória falhou.
- `não verificável`: faltam dados ou algoritmos necessários para concluir uma
  verificação obrigatória.

## Como preservar e apresentar

Mantenha juntos o ZIP original, seu checksum, os complementos probatórios e o
relatório exportado pelo verificador. O SHA-256 externo identifica exatamente o
arquivo analisado e permite demonstrar que todos trabalharam sobre os mesmos
bytes.

## Escopo da atestação

O Chitãozinho atesta integridade técnica, continuidade da coleta, vínculo entre
artefatos e sequência e, quando a prova correspondente estiver presente,
existência temporal dos bytes registrados. A apreciação jurídica considera
esse conjunto técnico junto ao contexto do caso.
