# Como o Chitãozinho produz uma evidência digital

Esta é a metodologia do Chitãozinho em linguagem simples. Ela explica o que
acontece desde o início da captura até a validação do pacote e por que cada
etapa foi construída dessa forma. O conteúdo corresponde à metodologia técnica
v0.2 incluída nos pacotes de evidência.

## A ideia central

Um print registra apenas uma imagem. O Chitãozinho registra uma sequência:
onde a navegação começou, o que apareceu na tela, quais ações aconteceram e
quais arquivos foram produzidos ao longo da coleta.

No final, tudo é reunido em um pacote de evidência. Esse pacote contém os
arquivos capturados e também os elementos necessários para conferir sua
integridade, sua ordem e sua história técnica.

É parecido com lacrar uma caixa, fazer uma lista de tudo que está dentro e
registrar cada pessoa que recebeu essa caixa. Se algo for trocado, retirado ou
colocado fora de ordem, a conferência deixa de bater.

## 1. Preparação da captura

### O que acontece

Antes de começar, o usuário escolhe a aba que será registrada e confirma que
está autorizado a coletar aquele conteúdo. A orientação é iniciar em uma página
que mostre a origem do material e navegar exibindo datas, endereços, perfis e
outros elementos de contexto.

### Por que fazemos assim

Uma imagem isolada pode mostrar uma frase sem mostrar quem publicou, onde ela
apareceu ou o que veio antes e depois. Registrar o contexto torna a evidência
mais completa e facilita sua análise posterior.

## 2. Registro da navegação

### O que acontece

Durante a captura, o Chitãozinho pode registrar:

- vídeo da aba;
- imagens da tela;
- estrutura da página;
- texto visível;
- endereço e título da página;
- tamanho da tela e da área visível;
- momentos marcados pelo usuário;
- mudanças de página e eventos de navegação.

Cada item registra também como foi coletado e se a coleta foi concluída. Se o
navegador impedir o acesso a algum elemento, essa ausência e seu motivo ficam
declarados no pacote.

### Por que fazemos assim

Formatos diferentes se complementam. O vídeo preserva a continuidade da
navegação; as imagens destacam momentos importantes; a estrutura e o texto da
página facilitam conferências técnicas; os metadados ajudam a entender o
ambiente da coleta.

Declarar uma ausência é melhor do que escondê-la. Assim, quem verifica o pacote
sabe exatamente quais elementos foram registrados e quais não estavam
disponíveis naquela captura.

## 3. Identificação de cada parte

### O que acontece

Cada arquivo ou parte de arquivo recebe uma identificação matemática chamada
hash SHA-256. O hash funciona como uma impressão digital dos bytes: o mesmo
conteúdo sempre produz o mesmo resultado.

Se um único byte mudar, o hash calculado depois será diferente.

### Por que fazemos assim

Nomes de arquivo podem ser repetidos e datas podem ser alteradas. O hash permite
identificar o conteúdo exato que foi registrado e detectar modificações
posteriores de maneira objetiva e reproduzível.

## 4. Encadeamento da sequência

### O que acontece

Os eventos da captura são colocados em uma cadeia. Cada novo evento guarda o
hash do evento anterior. Além disso, a extensão assina os eventos com uma chave
criada especialmente para aquela sessão.

### Por que fazemos assim

Esse encadeamento preserva a ordem da coleta. Se alguém remover, duplicar,
alterar ou trocar a posição de um evento, a ligação com os eventos seguintes
deixa de conferir.

É semelhante a um livro com páginas numeradas em que cada página também contém
um resumo da página anterior. Não basta renumerar uma folha: todas as ligações
seguintes precisariam continuar válidas.

## 5. Envio contínuo e recibos

### O que acontece

Enquanto a captura está em andamento, as partes são enviadas e preservadas
progressivamente. O servidor recalcula o hash recebido, armazena os bytes e só
então emite um recibo assinado.

Cada recibo informa qual parte foi recebida, qual era seu hash e em que posição
ela aparece na sequência.

### Por que fazemos assim

O envio contínuo reduz a dependência do dispositivo até o fim da gravação. Se o
navegador fechar ou a conexão cair, as partes já confirmadas continuam
registradas.

O recibo é emitido depois do armazenamento para ligar a confirmação do servidor
a bytes que ele efetivamente recebeu e preservou.

## 6. Fechamento da captura

### O que acontece

Quando o usuário finaliza, a extensão produz uma declaração de encerramento com
a sequência completa, os artefatos registrados e eventuais ausências. Essa
declaração é assinada pela chave da sessão.

O servidor confere a cadeia, as assinaturas, os hashes e os recibos. Em seguida,
produz e assina o manifesto da captura, que funciona como o inventário final da
evidência.

### Por que fazemos assim

O encerramento cria um ponto final claro. O manifesto reúne em um documento
verificável tudo que pertence à sessão e permite distinguir uma captura
completa de uma captura que possui ausências declaradas.

## 7. Provas de tempo

### O que acontece

O hash do manifesto pode ser enviado a fontes externas de tempo:

- uma autoridade de carimbo do tempo no padrão RFC 3161;
- o OpenTimestamps, que ancora hashes na blockchain do Bitcoin.

Esses serviços devolvem provas que podem ser conferidas separadamente. Quando
uma confirmação chega depois, ela é distribuída como complemento e o pacote
original permanece intacto.

### Por que fazemos assim

Usar fontes externas reduz a dependência exclusiva do relógio do computador ou
do servidor. A prova demonstra que aquele hash já existia até o marco temporal
confirmado.

Manter confirmações posteriores em complementos evita reescrever o ZIP que já
foi entregue. O arquivo original continua identificado pelo mesmo hash.

## 8. Preservação contra alteração e exclusão

### O que acontece

Em ambientes configurados para preservação probatória, originais e provas são
copiados para armazenamento com versionamento, criptografia e Object Lock. No
modo de retenção, o objeto fica protegido durante o prazo definido.

### Por que fazemos assim

Hashes permitem detectar alterações; o armazenamento imutável acrescenta uma
barreira operacional para impedir que os objetos preservados sejam alterados ou
apagados antes do término da retenção.

Essas proteções são usadas em conjunto porque cada uma cobre uma parte diferente
da cadeia de custódia técnica.

## 9. Montagem do pacote de evidência

### O que acontece

O Chitãozinho gera um ZIP contendo:

- os arquivos capturados;
- o manifesto da captura;
- a sequência de eventos;
- os recibos do servidor;
- as assinaturas e chaves públicas necessárias;
- a metodologia utilizada.

Provas temporais concluídas posteriormente acompanham o ZIP em um complemento
assinado, sem modificar o pacote original.

O pacote possui um índice assinado com o caminho, o tamanho e o hash de cada
arquivo. O ZIP também recebe um checksum SHA-256 externo.

### Por que fazemos assim

O pacote é autocontido: uma pessoa pode recebê-lo e fazer a conferência sem
precisar acessar a conta que originou a captura. O índice impede que arquivos
sejam acrescentados, removidos ou substituídos silenciosamente.

O checksum externo identifica o ZIP inteiro e permite confirmar que duas
pessoas receberam exatamente o mesmo arquivo.

## 10. Validação independente

### O que acontece

O verificador abre o pacote e refaz as conferências:

- compara o checksum externo, quando fornecido;
- valida o índice e a lista exata de arquivos;
- recalcula todos os hashes;
- verifica as assinaturas;
- percorre a cadeia na ordem correta;
- confere os recibos;
- identifica ausências declaradas;
- verifica as provas temporais disponíveis.

O verificador web processa tudo no navegador e não envia o conteúdo selecionado
ao Chitãozinho. A mesma aplicação funciona online ou offline. A ferramenta de
linha de comando permite realizar também as verificações criptográficas mais
especializadas.

### Por que fazemos assim

A evidência não deve depender apenas da afirmação de quem a produziu. A
verificação pode ser repetida por advogados, peritos, instituições ou outras
pessoas que recebam o pacote.

Processar os arquivos localmente preserva a confidencialidade e permite
trabalhar em ambientes sem conexão com a internet.

## Como interpretar o resultado

- **Íntegro:** as verificações obrigatórias foram concluídas e são válidas.
- **Íntegro, mas incompleto:** os elementos presentes são válidos e as
  ausências estão declaradas.
- **Inválido:** alguma conferência obrigatória falhou, como um hash ou uma
  assinatura divergente.
- **Não verificável:** faltam dados necessários para concluir uma conferência
  obrigatória.

Os estados das provas de tempo, retenção e blockchain são apresentados
separadamente. Assim, uma prova ainda pendente não é confundida com uma falha de
integridade dos arquivos já preservados.

## O que deve ser preservado

Mantenha juntos:

1. o ZIP original;
2. o arquivo `.sha256`;
3. os complementos de provas recebidos depois;
4. o relatório exportado pelo verificador.

Evite abrir o ZIP para salvar uma nova cópia ou substituir arquivos internos.
Para consultar o conteúdo, trabalhe sobre uma cópia e preserve o pacote original
exatamente como foi recebido.

## Escopo da atestação

O Chitãozinho atesta integridade técnica, continuidade da coleta, vínculo entre
artefatos e sequência e, quando a prova correspondente estiver presente,
existência temporal dos bytes registrados. A apreciação jurídica considera
esse conjunto técnico junto ao contexto do caso.
