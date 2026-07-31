# Chitãozinho e Verifact: paridade, diferenças e próximos passos

Este relatório compara o Chitãozinho com as capacidades atribuídas à Verifact
no laudo de auditoria emitido pela STWBrasil em 28 de março de 2024. O objetivo
é orientar produto e implementação, não reproduzir a comunicação do concorrente
nem emitir uma conclusão jurídica sobre qualquer das ferramentas.

O laudo analisado é um resumo conclusivo. Ele menciona evidências de testes em
um documento separado que não foi fornecido. Por isso, as capacidades da
Verifact abaixo representam o que o laudo afirma, e não uma verificação
independente realizada pela equipe do Chitãozinho.

| Capacidade | Verifact segundo o laudo | Chitãozinho hoje | Situação | Por que fazemos assim ou o que falta |
| --- | --- | --- | --- | --- |
| Entrada simples para o usuário | Plataforma online apresentada como intuitiva e acessível | Extensão instalada no navegador do usuário | Estratégias diferentes | A extensão é nosso primeiro passo por ser mais simples, acessível e compatível com sessões já autenticadas. |
| Vídeo da navegação | Sim, com áudio | WebM com vídeo e áudio da aba | Paridade | Preservamos o fluxo contínuo, além das imagens pontuais. |
| Screenshots | Sim | Inicial e adicionais sob comando do usuário | Paridade | Screenshots facilitam consulta e destacam momentos relevantes sem substituir o vídeo. |
| Texto, página e metadados | O laudo afirma coleta de textos, dados e metadados auditáveis | DOM, texto visível, URL, título, user agent, tela, viewport e fuso | Paridade parcial | Nossos metadados descrevem com precisão o que foi observado, mas URL e ambiente ainda são declarados pelo cliente. |
| Áudios, vídeos e imagens presentes na página | Sim | Preservados visualmente e pelo áudio da aba quando reproduzidos | Paridade parcial | A extensão registra a experiência apresentada na aba; não extrai automaticamente cada mídia como arquivo independente. |
| Arquivos baixados durante a sessão | Incluídos no resultado | Não são incorporados à evidência | Lacuna | Precisamos observar downloads, preservar os bytes e vinculá-los à sessão, com origem, tipo, tamanho e hash. |
| Orientação para coletar da fonte original | Recomendada | Incluída na interface e na metodologia simples | Paridade | Mostrar origem, endereço, perfil, datas e contexto fortalece o material coletado. |
| Ambiente isolado por coleta | O laudo afirma separação entre ambientes | A extensão opera no navegador normal do usuário | Diferença estratégica | Priorizamos alcance e baixa fricção. Um modo controlado deve ser uma modalidade adicional de maior garantia, não substituto da extensão. |
| Hashes e detecção de alteração | O laudo menciona chaves e criptografia internas | SHA-256 por parte, por artefato, manifesto e pacote | Paridade forte | Identificamos exatamente os bytes coletados e localizamos alterações posteriores. |
| Ordem e continuidade da coleta | Tratada como cadeia de custódia | Eventos encadeados, assinados e vinculados ao evento anterior | Paridade forte | Remoção, duplicação, alteração ou reordenação rompe a cadeia verificável. |
| Confirmação de persistência | Não detalhada no laudo | Recibo assinado somente depois de cada parte ser persistida | Chitãozinho à frente | O recibo associa a confirmação do servidor aos bytes que ele efetivamente armazenou. |
| Recuperação de interrupções | Não detalhada no laudo | Buffer local, retry idempotente e retomada de sessão | Chitãozinho à frente | Uma falha de rede ou da extensão não deve apagar silenciosamente o que já foi coletado. |
| Captura parcial | Não detalhada no laudo | Ausências e seus motivos entram no manifesto assinado | Chitãozinho à frente | Preferimos declarar uma lacuna a apresentar uma captura incompleta como se fosse integral. |
| Relatório técnico por captura | Relatório certificado com telas, dados, metadados e informações da sessão | Relatórios HTML e JSON de verificação | Paridade parcial | Falta um laudo humano completo, com narrativa da coleta, linha do tempo, telas e apresentação pronta para o processo. |
| Assinatura institucional | Assinatura ICP-Brasil com e-CNPJ | Assinaturas Ed25519 do cliente e servidor, com raiz offline e chave operacional | Lacuna institucional | Nosso modelo é aberto e tecnicamente verificável, mas ainda não vincula a assinatura à identidade empresarial ICP-Brasil. |
| Carimbo de tempo | ACT ICP-Brasil | RFC 3161 configurável, validado pelo verificador | Paridade técnica parcial | O mecanismo existe; falta selecionar, contratar e validar uma ACT ICP-Brasil para produção. |
| Âncora pública de tempo | Não mencionada | Merkle e OpenTimestamps na blockchain do Bitcoin | Chitãozinho à frente | Acrescentamos uma fonte pública independente sem publicar conteúdo ou identificadores de sessão. |
| Preservação sem reescrever o original | O laudo atribui imutabilidade ao carimbo e às proteções internas | Manifesto e pacote imutáveis; provas posteriores são complementos append-only | Paridade forte | Se uma prova temporal confirmar depois, ela não altera o ZIP que já foi distribuído. |
| Retenção contra alteração e exclusão | O laudo afirma preservação do material | Ceph RGW, criptografia e Object Lock `COMPLIANCE` implementados na aplicação | Paridade parcial | O código só informa `locked` após conferir a retenção, mas o ensaio real no Ceph externo ainda está pendente. |
| Chave protegida em HSM | e-CNPJ em HSM cloud na Azure | Chave Ed25519 não exportável no OpenBao Transit | Paridade arquitetural parcial | A integração existe, mas a chave de produção ainda não foi provisionada e auditada. |
| Criptografia em repouso e transporte | O laudo afirma criptografia interna e proteção no transporte | TLS obrigatório e criptografia server-side no storage probatório | Paridade parcial | Os controles estão implementados e possuem gates de configuração; falta validá-los no ambiente público completo. |
| Separação entre usuários | O laudo relata pentest sem acesso cruzado às provas | Magic link, owner isolation, URLs curtas e não enumeráveis | Paridade de aplicação parcial | Temos testes automatizados, mas ainda falta revisão externa do ambiente implantado. |
| Verificação sem depender do produtor | O laudo menciona possibilidade de contraditório, sem descrever verificador público | Verificador web e CLI abertos, online e offline | Chitãozinho à frente | Terceiros podem repetir a conferência sem autenticação e sem enviar os arquivos ao backend. |
| Formatos e metodologia públicos | Não detalhados no laudo | Schemas, vetores, metodologia e identidade do software versionados | Chitãozinho à frente | A transparência reduz dependência de afirmações do próprio fornecedor. |
| Repetibilidade e reprodutibilidade | O laudo afirma ensaios com operadores e ambientes diferentes | Vetores cruzados, builds reproduzíveis e smoke tests reais | Paridade parcial | Nossos testes cobrem o protocolo; ainda falta publicar um ensaio externo equivalente sobre o processo completo de coleta. |
| Pentest independente | O laudo afirma pentest sem vulnerabilidade capaz de manipular provas de terceiros | Revisão interna e scanners automatizados | Lacuna institucional | Precisamos de pentest externo com escopo, versão, ambiente, achados e reteste documentados. |
| Aderência à ISO/IEC 27037 e ao art. 158-B do CPP | Atestada no laudo por auditores externos | Requisitos orientaram a SPEC, sem parecer externo | Lacuna institucional | Precisamos de matriz requisito a requisito, evidências de ensaio e parecer independente sobre a versão implantada. |
| Interface administrativa | O laudo afirma documentação e acesso do operador às informações da coleta | Ainda não implementada | Lacuna | A administração deverá ser somente leitura, auditada e sem controles de edição ou exclusão. |

## Resumo executivo

O Chitãozinho já possui paridade no núcleo técnico necessário para produzir um
pacote verificável: vídeo com áudio, screenshots, DOM, texto, metadados, hashes,
assinaturas, encadeamento da sessão, recibos, recuperação de interrupções e
verificação offline.

Em transparência e verificabilidade independente, o Chitãozinho possui elementos
que não aparecem no laudo analisado: formatos públicos, vetores cruzados,
verificador aberto, recibos após persistência, captura parcial declarada,
attestations append-only e OpenTimestamps.

A principal diferença competitiva está fora do protocolo. A Verifact apresenta
um conjunto institucional já embalado para uso jurídico: relatório por coleta,
assinatura e-CNPJ, carimbo ICP-Brasil, pentest e parecer externo de aderência à
ISO/IEC 27037 e ao Código de Processo Penal. O Chitãozinho ainda precisa
transformar sua base técnica em uma operação implantada, auditada e comunicável
nesse mesmo nível.

## A extensão como primeiro modo de captura

A ausência de um ambiente controlado na primeira versão não deve ser descrita
apenas como uma deficiência. Ela é consequência de uma escolha de produto: a
extensão reduz a barreira de entrada e permite que a pessoa registre conteúdo no
contexto em que já o acessa.

Esse modo possui vantagens práticas:

- instalação e uso simples;
- menor custo operacional;
- uso da sessão já autenticada no navegador;
- acesso a mensageria, sistemas privados e conteúdos dependentes de login;
- suporte natural a MFA e fluxos interativos;
- nenhuma necessidade de entregar senhas ao Chitãozinho;
- operação compatível com uma infraestrutura self-hosted;
- captura feita sob controle direto do usuário.

A fronteira de confiança, porém, começa no que a extensão observa. O navegador,
o perfil, outras extensões, a conta e o sistema operacional do usuário não são
isolados ou atestados pelo Chitãozinho. Essa condição deve continuar registrada
tecnicamente no pacote, sem impedir que o modo seja útil como uma alternativa
muito mais robusta que um print isolado.

Por isso, a direção recomendada é oferecer dois níveis que compartilham o mesmo
formato de evidência:

### Modo essencial: extensão

- padrão para usuários individuais;
- instalação rápida e coleta no contexto real do usuário;
- apropriado para a POC e para grande parte dos usos cotidianos;
- mantém hashes, cadeia, recibos, provas de tempo e verificação independente;
- identifica a procedência como observação realizada no navegador do usuário.

### Modo controlado: garantia ampliada

- Chromium e configuração fixados por versão;
- perfil descartável criado para cada sessão;
- ausência de extensões de terceiros;
- isolamento entre coletas;
- evidência do estado inicial e da destruição do ambiente;
- logs de rede, DNS, TLS, redirecionamentos e respostas relevantes;
- execução local isolada ou em infraestrutura self-hosted;
- relatório identifica explicitamente que a coleta ocorreu em ambiente
  controlado.

O modo controlado não deve criar outro protocolo. Ele deve produzir os mesmos
eventos, recibos, manifestos e pacotes, acrescentando attestations sobre o
ambiente. Assim, ambos os modos continuam verificáveis pelas mesmas ferramentas.

## O que não devemos copiar sem análise

O laudo atribui ao carimbo de tempo tanto o registro do instante exato do acesso
quanto a imutabilidade dos dados. No desenho do Chitãozinho, essas propriedades
permanecem separadas:

- o hash identifica os bytes;
- a assinatura vincula uma declaração a uma chave;
- o carimbo demonstra que o hash já existia até determinado marco temporal;
- o Object Lock impede alteração ou exclusão durante a retenção;
- a sequência assinada demonstra continuidade da coleta.

Essa separação é mais precisa, facilita a auditoria e evita depender de uma única
tecnologia para alegar propriedades diferentes.

Também não devemos usar frases como “nenhum espaço para fraude” ou “validade
comprovada juridicamente” apenas porque aparecem em um parecer concorrente. A
comunicação pode e deve ser afirmativa, mas cada garantia pública precisa apontar
para um mecanismo, um teste ou uma auditoria identificável.

## Lacunas prioritárias

### 1. Colocar o núcleo probatório em ambiente público

- API e worker online;
- PostgreSQL com backup e restore operacional;
- Ceph RGW externo com Object Lock validado;
- chave operacional não exportável no OpenBao;
- autenticação por magic link e SMTP;
- monitoramento e alertas conectados;
- smoke test completo usando uma captura sintética.

### 2. Produzir um laudo técnico por captura

O laudo deve ser uma apresentação humana de documentos técnicos assinados, não
uma nova fonte de verdade. Ele deve conter:

- identificação e período da sessão;
- origem e contexto registrados;
- linha do tempo da navegação;
- screenshots representativas;
- inventário dos artefatos;
- hashes, assinaturas e recibos;
- completude e ausências declaradas;
- provas temporais e retenção;
- versão do software e da metodologia;
- QR Code ou link para o verificador;
- hash do ZIP ao qual o laudo se refere.

### 3. Adicionar identidade institucional ICP-Brasil

O modelo Ed25519 aberto deve permanecer. A ICP-Brasil entra como uma camada
adicional:

- selecionar e contratar uma ACT compatível com RFC 3161;
- assinar o laudo com e-CNPJ;
- avaliar assinatura ICP-Brasil também sobre o manifesto ou seu hash;
- preservar certificado, cadeia, política e material de validação;
- manter a verificação técnica possível sem software proprietário.

### 4. Ampliar a proveniência da coleta

- capturar arquivos baixados durante a sessão;
- registrar redirecionamentos e cabeçalhos relevantes;
- preservar informações de DNS, IP e certificado TLS quando disponíveis;
- definir um formato sanitizado para eventos de rede;
- vincular cada elemento ao evento e à aba que o originou;
- evitar registrar cookies, tokens ou cabeçalhos de autenticação.

### 5. Obter validação externa

- pentest independente do ambiente implantado;
- reteste após correções;
- ensaio formal de repetibilidade e reprodutibilidade;
- matriz ISO/IEC 27037 requisito por requisito;
- matriz das etapas aplicáveis do art. 158-B do CPP;
- parecer técnico independente com versão e escopo explícitos;
- revisão jurídica das afirmações usadas no produto e no laudo.

### 6. Implementar a operação administrativa

- listagem paginada de sessões e estados;
- visualização segura de imagens, vídeo, DOM e metadados;
- downloads auditados;
- separação rígida entre usuário e administrador;
- nenhuma edição ou exclusão de evidências;
- trilha append-only para toda consulta administrativa.

## Sequência recomendada

1. Finalizar o ambiente público e validar Ceph, OpenBao, autenticação e TSA.
2. Criar o laudo técnico por captura.
3. Incorporar ACT e assinatura institucional ICP-Brasil.
4. Capturar downloads e proveniência de rede.
5. Entregar a interface administrativa somente leitura.
6. Definir e prototipar o modo controlado como modalidade adicional.
7. Realizar pentest, ensaios forenses e parecer independente.

Essa sequência preserva a principal vantagem atual do Chitãozinho: entregar
primeiro uma ferramenta simples e acessível, sustentada por um protocolo forte,
e acrescentar gradualmente níveis maiores de garantia sem quebrar o pacote ou o
verificador já existentes.

## Referências internas

- [Contrato do produto](../SPEC.md)
- [Critérios de aceite](../ACEITE.md)
- [Metodologia em linguagem simples](metodologia-em-linguagem-simples.md)
- [Registros de smoke tests](smoke-tests.md)
- [Revisão de segurança](security-review.md)
- [Avaliação de autoridades de carimbo do tempo](tsa-evaluation.md)
- [Retenção de evidências](retention.md)
