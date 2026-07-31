# SPEC.md — Plataforma de Captura e Preservação de Evidências Digitais

**Status:** Draft v0.2
**Data:** 30/07/2026
**Nome provisório:** Chitãozinho
**Escopo inicial:** Captura de conteúdos exibidos em navegador, preservação de integridade, registro temporal e geração de pacote probatório verificável.

---

## 1. Visão geral

A plataforma permite que uma pessoa capture conteúdo digital exibido em uma página web e gere um pacote técnico verificável contendo:

- screenshots;
- gravação da sessão de navegação;
- HTML/DOM e metadados acessíveis;
- URL, título da página e dados do navegador;
- cadeia de hashes da captura;
- manifesto assinado;
- carimbo de tempo;
- prova de ancoragem em blockchain;
- recibos emitidos pelo servidor durante a captura;
- relatório humano de verificação.

O objetivo não é afirmar que o conteúdo capturado é verdadeiro em sentido material, mas demonstrar, com alta confiabilidade técnica, que:

1. determinados bytes foram capturados por um software identificado;
2. a coleta ocorreu em uma sequência documentada;
3. o conteúdo não foi alterado após cada etapa registrada;
4. o pacote já existia antes de determinados registros temporais externos;
5. a verificação pode ser feita de forma independente.


---

## 2. Princípios de projeto

### 2.1 Verificabilidade independente

A validade técnica do pacote não deve depender exclusivamente do servidor da plataforma. O verificador deve ser open source e executar localmente.

### 2.2 Não confiança no backend

Sempre que possível, o cliente calcula hashes antes do upload. O servidor recebe e assina os hashes, mas não é a única fonte de verdade.

### 2.3 Preservação do original

Arquivos originais nunca são substituídos. Qualquer transformação, conversão, compactação ou geração de preview cria um novo artefato com hash próprio.

### 2.4 Minimização de dados

Nenhum conteúdo privado deve ser publicado em blockchain. Apenas hashes, raízes de Merkle ou compromissos criptográficos podem sair do ambiente controlado.

### 2.5 Transparência metodológica

O formato do pacote, algoritmos, versão do software e procedimentos de verificação devem ser públicos e documentados.

### 2.6 Defesa em profundidade

A solução combina diferentes mecanismos:

- hash criptográfico;
- cadeia de hashes;
- assinatura digital;
- recibos sequenciais;
- armazenamento WORM;
- carimbo de tempo externo;
- ancoragem em blockchain;
- logs append-only;
- verificador independente.

Nenhum mecanismo isolado deve ser tratado como suficiente.

---

## 3. Escopo

### 3.1 POC funcional

A primeira entrega deve validar o fluxo completo sem depender de infraestrutura de produção:

- Extensão para Chromium.
- Captura de uma aba do navegador.
- Screenshot por viewport.
- Gravação contínua da aba, mediante autorização do usuário.
- Coleta de URL, título, timestamps, user agent, resolução e timezone, identificados como dados declarados pelo cliente.
- Coleta de HTML/DOM quando permitido.
- Registro básico de navegação, rolagem e mudanças de URL.
- Hash SHA-256 de partes e artefatos no cliente.
- Upload em blocos com retomada.
- Recibos sequenciais assinados pelo servidor.
- Manifesto de captura JSON assinado.
- Geração de pacote ZIP probatório.
- CLI local de verificação.
- Relatório HTML de verificação.
- PostgreSQL e Garage, via protocolo S3 compatível, para desenvolvimento local.

### 3.2 POC probatória completa

Após o fluxo funcional estar validado:

- carimbo de tempo RFC 3161;
- árvore de Merkle e ancoragem via OpenTimestamps/Bitcoin;
- attestations e complementos assinados;
- armazenamento Ceph RGW com Object Lock em ambiente de teste;
- validação integrada de indisponibilidade e retomada dos serviços externos.

### 3.3 Fora da POC

- Aplicativo desktop nativo.
- Captura de aplicativos fora do navegador.
- Captura de aparelhos móveis.
- Extração forense de dispositivos.
- Validação de identidade do autor do conteúdo.
- Certificação de que um perfil pertence a determinada pessoa.
- Detecção garantida de manipulação anterior à captura.
- Integração direta com cartórios.
- Emissão automática de ata notarial.
- Perícia automatizada.
- Reconhecimento jurídico automático.
- Relatório PDF.
- Autenticação institucional, RBAC, MFA e gestão multi-organização.
- Retenção `COMPLIANCE` com dados reais.

### 3.4 Evoluções previstas

- Agente desktop em Rust/Tauri.
- Aplicativo Android.
- Assinatura com chaves protegidas por hardware.
- Atestação de dispositivo.
- Integração com ICP-Brasil.
- Modo institucional para escritórios, organizações e órgãos públicos.
- API de captura automatizada para páginas públicas.
- Exportação em formatos compatíveis com ferramentas forenses.

---

## 4. Personas

### 4.1 Usuário coletor

Pessoa que deseja registrar conteúdo digital antes que ele seja apagado ou alterado.

Necessidades:

- iniciar uma captura rapidamente;
- visualizar o que está sendo coletado;
- receber um pacote verificável;
- entender os limites da evidência;
- compartilhar o resultado com advogado, jornalista, organização ou autoridade.

### 4.2 Verificador

Advogado, perito, magistrado, jornalista, auditor ou terceiro que recebe um pacote.

Necessidades:

- confirmar integridade dos arquivos;
- validar assinaturas;
- verificar carimbos de tempo;
- verificar prova blockchain;
- identificar arquivos ausentes ou alterados;
- gerar relatório compreensível.

### 4.3 Administrador institucional

Organização que gerencia usuários, políticas de retenção e permissões.

Necessidades:

- configurar retenção;
- auditar atividades;
- controlar acesso;
- exportar registros;
- manter separação entre organizações.

---

## 5. Modelo de ameaça

### 5.1 Ameaças consideradas

- Alteração de arquivos após a captura.
- Exclusão de evidências.
- Substituição silenciosa de arquivos.
- Reordenação ou remoção de blocos da gravação.
- Retrodatação de um pacote.
- Comprometimento posterior do backend.
- Administrador tentando reescrever o histórico.
- Interrupção de conexão durante a captura.
- Pacote incompleto apresentado como completo.
- Verificador usando uma versão não confiável do software.

### 5.2 Ameaças parcialmente mitigadas

- Página manipulada localmente antes da captura.
- Navegador comprometido.
- Extensão adulterada.
- Sistema operacional comprometido.
- Perfil falso ou conta clonada.
- Conteúdo gerado em ambiente emulado.

### 5.3 Ameaças não resolvidas pela plataforma

- Autoria material da mensagem.
- Veracidade dos fatos mostrados.
- Legalidade da obtenção do conteúdo.
- Interpretação jurídica final.
- Integridade física do dispositivo antes do início da captura.

### 5.4 Declaração obrigatória

Todo relatório deve incluir:

> Este pacote demonstra a integridade e a rastreabilidade técnica dos artefatos a partir do momento em que foram processados pelo sistema.

---

## 6. Arquitetura

```text
┌──────────────────────┐
│ Extensão Chromium    │
│                      │
│ - captura            │
│ - hash local         │
│ - assinatura cliente │
│ - upload em blocos   │
└──────────┬───────────┘
           │ HTTPS
           ▼
┌──────────────────────┐
│ API Backend          │
│                      │
│ - cria sessão        │
│ - emite desafio      │
│ - assina recibos     │
│ - fecha manifesto    │
└───────┬───────┬──────┘
        │       │
        │       ├───────────────┐
        ▼                       ▼
┌───────────────┐       ┌────────────────┐
│ PostgreSQL    │       │ Ceph RGW       │
│ append-only   │       │ WORM           │
└───────────────┘       └────────────────┘
        │
        ├───────────────┐
        ▼               ▼
┌───────────────┐  ┌────────────────────┐
│ RFC 3161 TSA  │  │ Merkle Aggregator  │
│ timestamp     │  │ OpenTimestamps     │
└───────────────┘  └────────────────────┘

┌──────────────────────┐
│ Verificador local    │
│                      │
│ - CLI                │
│ - Web offline        │
│ - relatório          │
└──────────────────────┘
```

---

## 7. Componentes

### 7.1 Extensão Chromium

Responsabilidades:

- autenticar o usuário;
- solicitar criação de sessão;
- receber desafio aleatório do servidor;
- solicitar permissões de captura;
- capturar artefatos;
- calcular hashes localmente;
- encadear blocos;
- assinar eventos com chave efêmera da sessão;
- assinar a declaração de encerramento da captura;
- enviar artefatos e metadados;
- receber recibos assinados;
- mostrar estado e erros;
- finalizar a sessão.

Tecnologias sugeridas:

- TypeScript;
- Manifest V3;
- React;
- Web Crypto API;
- MediaRecorder API;
- chrome.tabs;
- `chrome.debugger` fora da POC; qualquer adoção futura exige consentimento e revisão de segurança;
- IndexedDB para buffer local.

Na POC, a extensão é instalada unpacked. Todo build registra versão, commit e hash do pacote no manifesto; distribuição pela Chrome Web Store fica para etapa posterior.

### 7.2 Backend

Responsabilidades:

- autenticação;
- criação e encerramento de sessões;
- emissão de desafios aleatórios;
- recálculo dos hashes a partir dos bytes recebidos;
- emissão de recibos sequenciais;
- persistência de eventos;
- upload multipart;
- geração do manifesto de captura;
- geração de attestations e complementos;
- assinatura do servidor;
- integração com TSA;
- agregação Merkle;
- submissão ao OpenTimestamps;
- geração do pacote;
- política de retenção;
- API de verificação.

Tecnologias sugeridas:

- Python 3.13 + FastAPI para POC;
- PostgreSQL;
- jobs persistidos no PostgreSQL na primeira versão;
- Redis e worker dedicado apenas quando carga ou isolamento justificarem;
- Ceph RGW compatível com S3 e Object Lock;
- libsodium ou biblioteca Ed25519 consolidada;
- Docker/OCI.

Evolução condicionada a necessidade comprovada de desempenho ou isolamento:

- Rust + Axum;
- PostgreSQL;
- NATS ou Kafka para eventos;
- serviço dedicado de assinatura.

### 7.3 Verificador

Responsabilidades:

- abrir pacote ZIP;
- tratar o pacote como entrada não confiável;
- validar estrutura;
- recalcular todos os hashes;
- validar cadeia de blocos;
- validar assinaturas;
- validar recibos;
- verificar token RFC 3161;
- verificar prova OpenTimestamps;
- verificar prova de inclusão Merkle;
- reportar inconsistências;
- gerar resultado legível por humanos.

Requisitos de segurança:

- rejeitar path traversal, links simbólicos e nomes duplicados;
- impor limites de arquivos, tamanho total, expansão, profundidade de JSON e uso de memória;
- não extrair conteúdo fora de um diretório temporário isolado;
- falhar de forma localizada para schemas e algoritmos desconhecidos.

Formatos:

- CLI em Rust;
- binários para Linux, Windows e macOS;
- versão web offline usando WebAssembly;
- código-fonte público.

---

## 8. Fluxo de captura

### 8.1 Início

1. Usuário abre a extensão.
2. Usuário escolhe “Nova captura”.
3. A extensão informa claramente quais dados serão registrados.
4. O backend cria uma sessão.
5. O backend retorna:
   - `session_id`;
   - `server_challenge`;
   - horário do servidor;
   - política de retenção;
   - chave pública do servidor;
   - número inicial da sequência.
6. A extensão gera um par de chaves efêmero Ed25519.
7. A chave pública da sessão é registrada no backend.
8. O evento de início é assinado pelo cliente e pelo servidor.

### 8.2 Captura

Durante a sessão, a extensão pode coletar:

- vídeo da aba;
- screenshots;
- URL atual;
- título da página;
- favicon;
- user agent;
- timezone;
- resolução;
- viewport;
- alterações de URL;
- timestamps monotônicos;
- HTML serializado;
- texto visível;
- eventos de rolagem;
- hashes de recursos baixados;
- certificados e dados de conexão, quando disponíveis.

Cada artefato registra:

- método de captura;
- origem;
- intervalo temporal coberto;
- permissões utilizadas;
- status `captured`, `unavailable`, `failed` ou `not_requested`;
- motivo de ausência ou falha;
- procedência `client_reported`, `server_observed` ou `externally_attested`.

HTML/DOM serializado representa o estado observado pelo navegador, não os bytes originais servidos pela origem. URL, user agent, timezone e relógio de parede do cliente são dados declarados pelo cliente. Canvas, WebGL, iframes, DRM e conteúdo protegido podem resultar em captura parcial e devem ser sinalizados.

Cada parte de artefato recebe:

- número sequencial;
- identificador e número da parte;
- timestamp monotônico do cliente;
- identificador da época do relógio monotônico;
- timestamp de parede do cliente;
- hash da parte;
- hash do evento anterior;
- desafio da sessão;
- assinatura do cliente.

### 8.3 Recibo do servidor

Para cada parte ou lote persistido de forma durável, o servidor retorna:

- `session_id`;
- `sequence`;
- identificador do artefato e da parte;
- hash recalculado pelo servidor;
- hash da entrada recebida;
- hash do recibo anterior;
- horário do servidor;
- estado de persistência;
- assinatura do servidor.

O recibo é persistido localmente e incluído no pacote final.

O reenvio da mesma sequência com o mesmo hash é idempotente e retorna o mesmo recibo lógico. A mesma sequência com conteúdo ou hash diferente retorna conflito e marca a sessão para revisão. Um recibo confirma apenas o estado de persistência declarado; não implica, por si só, retenção WORM.

### 8.4 Encerramento

1. O cliente envia evento `capture_finished`.
2. O servidor confirma que não há lacunas na sequência.
3. Cliente e servidor calculam independentemente a raiz da sessão.
4. O cliente assina uma declaração `capture_close` com a raiz, o último hash, a contagem de entradas e a lista final de artefatos.
5. O servidor valida a declaração e gera o manifesto de captura.
6. O servidor assina o manifesto, que se torna imutável.
7. O pacote funcional pode ser gerado e verificado localmente.
8. Na POC probatória completa, o hash do manifesto assinado recebe carimbo RFC 3161.
9. Uma attestation referencia o hash do manifesto e os artefatos de timestamp.
10. O hash atestado entra em uma árvore de Merkle, cuja raiz é enviada ao OpenTimestamps.
11. Confirmações posteriores geram complementos assinados; o manifesto e o pacote original não são alterados.

---

## 9. Cadeia de hashes

### 9.1 Algoritmo

Usar SHA-256 na POC.

### 9.2 Estrutura

Definições:

- `part_hash`: SHA-256 dos bytes exatos de uma parte enviada;
- `artifact_hash`: SHA-256 dos bytes exatos do artefato completo, na ordem original;
- `entry_hash`: SHA-256 da representação canônica de uma entrada da sessão;
- `session_root`: `entry_hash` da última entrada válida da sequência;
- `receipt_hash`: SHA-256 da representação canônica de um recibo, sem sua assinatura.

```text
entry_hash = SHA256(
  canonical_json({
    protocol_version,
    entry_type,
    session_id,
    sequence,
    artifact_id,
    part_number,
    part_hash,
    artifact_hash,
    previous_entry_hash,
    client_clock_id,
    client_monotonic_time,
    client_wall_time,
    server_challenge
  })
)
```

Campos não aplicáveis a determinado `entry_type` são omitidos conforme o schema, nunca preenchidos implicitamente. A primeira entrada usa `previous_entry_hash: null`. A POC usa uma sequência global por sessão; concorrência de uploads não altera a ordem lógica das entradas.

`client_monotonic_time` só é comparável dentro do mesmo `client_clock_id`. Se a extensão ou seu contexto reiniciar, ela cria uma nova época e registra um evento `clock_restarted`; não tenta simular continuidade monotônica.

Ao concluir um artefato, cliente e servidor recalculam `artifact_hash` sobre os bytes completos. Uma lista de hashes de partes não substitui o hash do artefato.

### 9.3 Canonicalização

Todo JSON usado em hash ou assinatura deve ser serializado com JSON Canonicalization Scheme, RFC 8785, em UTF-8. A implementação deve definir:

- Base64URL sem padding para bytes binários;
- hash em hexadecimal minúsculo com prefixo de algoritmo, por exemplo `sha256:...`;
- timestamps de parede em RFC 3339 com offset explícito;
- tempo monotônico como inteiro de microssegundos desde o início da sessão;
- identificadores de algoritmo e versão de protocolo;
- separação de domínio para cada assinatura, por exemplo `CHITAOZINHO/ENTRY/v1`.

Assinaturas são calculadas sobre os bytes ASCII do prefixo de domínio concatenados aos 32 bytes brutos do digest. Nenhuma biblioteca pode assinar uma serialização própria ou dependente da linguagem.

### 9.4 Recibos

```text
receipt_hash = SHA256(
  canonical_json({
    protocol_version,
    session_id,
    sequence,
    entry_hash,
    artifact_id,
    part_number,
    part_hash,
    previous_receipt_hash,
    server_time,
    persistence_state
  })
)
```

O servidor assina `CHITAOZINHO/RECEIPT/v1 || receipt_hash`. Os schemas devem definir os estados de persistência aceitos e os códigos de conflito.

### 9.5 Vetores de teste

Antes da integração entre extensão, backend e verificador, o repositório deve conter vetores públicos com:

- JSON de entrada;
- bytes canônicos esperados;
- hashes esperados;
- chaves de teste;
- assinaturas esperadas;
- casos inválidos.

TypeScript, Python e Rust devem produzir os mesmos resultados byte a byte.

### 9.6 Encerramento da captura

`capture_close` contém, no mínimo:

- versão do protocolo;
- `session_id`;
- `session_root`;
- último `entry_hash`;
- quantidade total de entradas;
- lista ordenada de artefatos com tamanho, status e `artifact_hash`, quando capturado;
- lista de lacunas e falhas conhecidas;
- chave pública efêmera e `key_id` da sessão.

O cliente assina `CHITAOZINHO/CAPTURE_CLOSE/v1 || SHA256(canonical_json(capture_close))`.

### 9.7 Propriedades

A cadeia deve tornar detectáveis:

- remoção de bloco;
- inserção de bloco;
- alteração de bloco;
- reordenação;
- duplicação;
- substituição.

---

## 10. Assinaturas digitais

### 10.1 Cliente

- Ed25519.
- Chave efêmera por sessão na POC.
- Chave privada armazenada apenas até a assinatura de `capture_close`.
- O cliente assina entradas da sessão e a declaração de encerramento, não o manifesto criado pelo servidor.
- Evolução futura: chave persistente protegida por hardware.

### 10.2 Servidor

- Ed25519.
- Chave armazenada em KMS/HSM quando possível.
- Rotação de chave documentada.
- Chaves públicas históricas mantidas indefinidamente.
- Cada assinatura identifica algoritmo e `key_id`.

### 10.3 Âncora de confiança

Receber a chave pública pelo mesmo backend não estabelece confiança independente. Na POC:

- o verificador inclui ou recebe explicitamente uma chave raiz confiável;
- chaves operacionais do servidor são assinadas pela chave raiz;
- o pacote inclui a chave operacional, seu certificado interno, validade e `key_id`;
- a chave raiz é gerada e mantida offline;
- chaves operacionais são rotacionadas a cada 90 dias e protegidas por KMS/HSM em produção;
- rotação e revogação geram registros assinados preservados historicamente;
- modo de confiança customizada deve ser explícito na CLI e no relatório.

### 10.4 Identidade do usuário

A assinatura da sessão não deve ser confundida com assinatura ICP-Brasil do usuário. Ela demonstra continuidade criptográfica da sessão, não identidade civil.

---

## 11. Carimbo de tempo

### 11.1 Requisito

O sistema deve suportar carimbo RFC 3161 emitido por autoridade externa.

Qualquer TSA RFC 3161 confiável pode ser usada na POC. Antes da produção, opções brasileiras devem ser comparadas. O verificador mantém trust store explícito e versionado; atualizações do trust store são assinadas.

### 11.2 Objeto carimbado

Carimbar o SHA-256 dos bytes exatos do manifesto de captura assinado pelo servidor. O manifesto não contém o resultado do próprio timestamp.

### 11.3 Armazenamento

Salvar:

- requisição `.tsq`;
- resposta `.tsr`;
- certificado da autoridade;
- cadeia de certificados;
- política utilizada;
- data de validação.

### 11.4 Falha do serviço

Se a TSA estiver indisponível:

- a sessão pode ser encerrada;
- `timestamp_status` recebe `pending`;
- o hash final não pode ser alterado;
- novas tentativas usam exatamente o mesmo hash;
- cada tentativa fica registrada.

O relatório diferencia:

- horários declarados pelo cliente;
- horários dos recibos do servidor;
- `genTime` informado pela TSA;
- limite temporal demonstrado pela blockchain.

Timestamp e blockchain demonstram que o hash existia até determinado momento; não demonstram que a captura ocorreu exatamente naquele instante.

---

## 12. Blockchain e OpenTimestamps

### 12.1 Objetivo

Criar uma prova pública e independente de que determinado hash existia antes da confirmação de um bloco.

### 12.2 Estratégia

- Não publicar um hash por captura.
- Agrupar hashes de sessões em árvores de Merkle.
- Publicar apenas a raiz agregada.
- Gerar prova individual de inclusão para cada sessão.
- Ancorar a raiz via OpenTimestamps na blockchain do Bitcoin.
- Agregar a cada hora ou 100 sessões, o que ocorrer primeiro, usando calendários públicos.

### 12.3 Privacidade

Não publicar:

- screenshots;
- textos;
- URLs;
- nomes;
- e-mails;
- números de telefone;
- identificadores de sessão reversíveis;
- metadados pessoais.

### 12.4 Status

Possíveis estados:

- `not_submitted`;
- `submitted`;
- `pending_confirmation`;
- `confirmed`;
- `verification_failed`.

### 12.5 Atualização da prova

A confirmação blockchain pode ocorrer após o fechamento inicial do pacote. Nesse caso:

- o pacote original permanece intacto;
- uma nova attestation ou complemento assinado é gerado;
- o complemento referencia o hash do pacote original;
- o complemento contém a prova `.ots` atualizada.

### 12.6 Attestations

`attestation.json` referencia o hash do manifesto de captura e pode conter:

- token e cadeia RFC 3161;
- prova de inclusão Merkle;
- prova e status OpenTimestamps;
- horários de consulta;
- chave e assinatura do emissor;
- referência à attestation anterior, quando houver.

Attestations são append-only. Uma atualização de estado cria um novo documento; nunca modifica o manifesto, uma attestation anterior ou o pacote já distribuído.

---

## 13. Armazenamento WORM/Object Lock

### 13.1 Requisitos

- Versionamento habilitado.
- Object Lock habilitado na criação do bucket.
- Retenção configurável.
- Modo `COMPLIANCE` para evidências finais.
- Legal hold opcional.
- Criptografia em repouso.
- Política de acesso mínimo.

### 13.2 Objetos protegidos

- arquivos capturados;
- manifesto;
- assinaturas;
- recibos;
- tokens de timestamp;
- provas blockchain;
- logs finais;
- relatórios de verificação.

### 13.3 Retenção

Valores iniciais sugeridos:

- gratuito: 90 dias;
- individual pago: 5 anos;
- institucional: configurável;
- legal hold: prazo indeterminado até liberação autorizada.

### 13.4 Exclusão

A interface deve informar que, no modo compliance, a exclusão pode ser tecnicamente impossível antes do fim do prazo.

---

## 14. Banco de dados append-only

### 14.1 Eventos

Todos os eventos relevantes devem ser registrados:

- sessão criada;
- chave registrada;
- captura iniciada;
- bloco recebido;
- recibo emitido;
- upload concluído;
- sessão encerrada;
- manifesto gerado;
- timestamp solicitado;
- timestamp recebido;
- raiz Merkle criada;
- blockchain submetida;
- blockchain confirmada;
- pacote baixado;
- verificação realizada;
- política de retenção aplicada.

### 14.2 Regra

Eventos não são atualizados nem apagados. Correções são novos eventos que referenciam eventos anteriores.

### 14.3 Integridade

Cada evento inclui o hash do evento anterior do mesmo stream.

---

## 15. Formato do pacote probatório

Usar ZIP com ZIP64 automático quando tamanho ou quantidade de arquivos exigirem.

```text
chitaozinho-evidence-<session_id>.zip
├── README.txt
├── package-index.json
├── capture-manifest.json
├── signatures/
│   ├── capture-close.client.sig
│   ├── capture-manifest.server.sig
│   ├── package-index.server.sig
│   └── public-keys.json
├── capture/
│   ├── recording.webm
│   ├── screenshot-0001.png
│   ├── screenshot-0002.png
│   ├── page.html
│   ├── visible-text.txt
│   └── metadata.json
├── chain/
│   ├── entries.jsonl
│   ├── receipts.jsonl
│   └── capture-close.json
├── timestamp/
│   ├── manifest.tsq
│   ├── manifest.tsr
│   └── tsa-chain.pem
├── blockchain/
│   ├── merkle-proof.json
│   ├── proof.ots
│   └── status.json
├── attestations/
│   └── attestation-0001.json
├── reports/
│   └── verification.html
└── schema/
    ├── entry.schema.json
    ├── chain-record.schema.json
    ├── receipt.schema.json
    ├── receipt-record.schema.json
    ├── capture-close.schema.json
    ├── manifest.schema.json
    ├── attestation.schema.json
    ├── package-index.schema.json
    └── version.txt
```

Diretórios de timestamp, blockchain e attestations podem estar ausentes no pacote funcional e são obrigatórios apenas quando o status correspondente indicar que a integração foi executada.

`package-index.json` lista caminho, tamanho, media type e hash de todos os membros do pacote, exceto ele próprio e sua assinatura. A assinatura do índice protege também relatórios e provas derivadas que não fazem parte do manifesto de captura.

### 15.1 Imutabilidade do pacote

O ZIP final recebe hash próprio. Qualquer atualização posterior deve ser distribuída como complemento, nunca sobrescrevendo o arquivo original.

O hash do ZIP é distribuído em recibo ou arquivo destacado, fora do próprio ZIP. O manifesto não tenta incluir o hash do contêiner que o contém. Relatórios internos verificam o conteúdo coberto pelo manifesto, não o hash externo do ZIP.

---

## 16. Manifesto de captura

Exemplo simplificado:

```json
{
  "schema_version": "0.1.0",
  "session_id": "01K1EXAMPLE",
  "status": "complete",
  "capture": {
    "started_at_client": "2026-07-30T14:18:00-03:00",
    "ended_at_client": "2026-07-30T14:22:51-03:00",
    "started_at_server": "2026-07-30T17:18:02Z",
    "ended_at_server": "2026-07-30T17:22:53Z",
    "software": {
      "name": "Chitãozinho Chromium Extension",
      "version": "0.1.0",
      "build_hash": "sha256:..."
    }
  },
  "artifacts": [
    {
      "path": "capture/recording.webm",
      "size": 10485760,
      "media_type": "video/webm",
      "sha256": "..."
    }
  ],
  "chain": {
    "first_hash": "...",
    "last_hash": "...",
    "entry_count": 84,
    "root_hash": "..."
  },
  "capture_close": {
    "path": "chain/capture-close.json",
    "client_signature_path": "signatures/capture-close.client.sig"
  },
  "limitations": [
    "The package does not prove authorship of displayed content.",
    "The package does not prove that the displayed content is factually true."
  ]
}
```

---

## 17. API

### 17.1 Criar sessão

`POST /v1/sessions`

Resposta:

```json
{
  "session_id": "01K1EXAMPLE",
  "server_challenge": "base64...",
  "server_time": "2026-07-30T17:18:02Z",
  "upload_policy": {},
  "retention_policy": {},
  "server_public_key_id": "srv-2026-01"
}
```

### 17.2 Registrar chave da sessão

`POST /v1/sessions/{session_id}/keys`

### 17.3 Enviar evento

`POST /v1/sessions/{session_id}/events`

Requer chave de idempotência e sequência lógica. Repetição idêntica retorna o resultado anterior; divergência retorna `409 Conflict`.

### 17.4 Enviar bloco

`PUT /v1/sessions/{session_id}/artifacts/{artifact_id}/parts/{part_number}`

Requer `part_hash`, tamanho declarado e chave de idempotência. O servidor recalcula o hash antes de emitir o recibo.

### 17.5 Finalizar artefato

`POST /v1/sessions/{session_id}/artifacts/{artifact_id}/complete`

### 17.6 Finalizar sessão

`POST /v1/sessions/{session_id}/finalize`

Requer a declaração `capture_close` e sua assinatura pelo cliente.

### 17.7 Obter status

`GET /v1/sessions/{session_id}`

### 17.8 Baixar pacote

`GET /v1/sessions/{session_id}/package`

### 17.9 Verificar pacote remotamente

`POST /v1/verify`

O verificador remoto é opcional e nunca substitui o verificador local.

### 17.10 Obter attestations

`GET /v1/sessions/{session_id}/attestations`

Retorna documentos append-only sem alterar o pacote original.

---

## 18. Estados

Estados de captura:

```text
created
  ↓
key_registered
  ↓
capturing
  ↓
uploading
  ↓
finalizing
  ↓
complete
```

Estados excepcionais de captura:

- `interrupted`;
- `incomplete`;
- `invalid_chain`;
- `upload_failed`;

Uma sessão incompleta não deve ser apresentada como inválida. Ela deve ser apresentada como captura parcial, indicando claramente quais garantias permanecem verificáveis.

Estados independentes:

- `package_status`: `not_generated`, `generating`, `available`, `failed`;
- `timestamp_status`: `not_requested`, `pending`, `valid`, `invalid`, `failed`;
- `blockchain_status`: `not_submitted`, `submitted`, `pending_confirmation`, `confirmed`, `verification_failed`;
- `storage_status`: `staging`, `stored`, `locked`, `retention_failed`.

Uma captura pode estar `complete` e disponível para verificação enquanto timestamp, blockchain ou retenção ainda estão pendentes. Cada transição gera um novo evento e, quando altera garantias externas, uma nova attestation.

---

## 19. Requisitos funcionais

### RF-001

O sistema deve permitir iniciar uma sessão de captura a partir da extensão.

### RF-002

O sistema deve registrar o consentimento do usuário para captura de tela e metadados.

### RF-003

O cliente deve calcular SHA-256 antes ou durante o upload.

### RF-004

O cliente deve encadear os eventos da sessão.

### RF-005

O servidor deve emitir recibo assinado para blocos ou lotes recebidos.

### RF-006

O sistema deve detectar lacunas, duplicações e reordenações.

### RF-007

O sistema deve preservar arquivos originais sem transformação destrutiva.

### RF-008

O sistema deve gerar manifesto de captura assinado pelo servidor e vinculado à declaração `capture_close` assinada pelo cliente.

### RF-009

O sistema deve solicitar carimbo RFC 3161.

### RF-010

O sistema deve gerar prova de inclusão em árvore de Merkle.

### RF-011

O sistema deve ancorar a raiz via OpenTimestamps.

### RF-012

O sistema deve armazenar artefatos finais em modo WORM.

### RF-013

O sistema deve gerar pacote ZIP autocontido.

### RF-014

O verificador local deve recalcular e validar todos os hashes.

### RF-015

O verificador deve funcionar sem autenticação e sem acesso ao backend para as verificações locais.

### RF-016

O relatório deve diferenciar integridade técnica, existência temporal e autenticidade material.

### RF-017

O sistema deve registrar a versão exata da extensão e do backend.

### RF-018

O sistema deve permitir capturas incompletas, marcadas como tais.

### RF-019

O usuário deve poder baixar o pacote e as chaves públicas necessárias para verificação.

### RF-020

A plataforma deve manter chaves públicas históricas e política de rotação.

### RF-021

O sistema deve registrar método, procedência e completude de cada artefato.

### RF-022

Uploads e eventos devem ser idempotentes e detectar reutilização divergente de sequência ou chave.

### RF-023

Timestamp, blockchain e retenção devem ser representados por estados independentes da conclusão da captura.

### RF-024

Atualizações de provas externas devem gerar attestations ou complementos append-only.

### RF-025

O verificador deve impor limites de recursos e rejeitar estruturas de pacote inseguras.

---

## 20. Requisitos não funcionais

### RNF-001 — Segurança

Todo tráfego deve usar TLS moderno.

### RNF-002 — Privacidade

Conteúdo não deve ser usado para treinamento de modelos ou análise comercial sem consentimento explícito separado.

### RNF-003 — Disponibilidade

A interrupção do backend não deve apagar o buffer local da sessão em andamento.

### RNF-004 — Auditabilidade

Toda versão do software deve possuir hash de build e changelog.

Logs não devem incluir conteúdo capturado, URLs completas, tokens, chaves ou dados pessoais por padrão.

### RNF-005 — Portabilidade

O pacote deve permanecer verificável fora da plataforma.

### RNF-006 — Desempenho

A captura não deve consumir CPU ou memória a ponto de comprometer significativamente a página registrada.

Hash e upload de vídeos devem ser incrementais; a implementação não pode exigir que todo o vídeo seja carregado simultaneamente na memória.

### RNF-007 — Escalabilidade

O backend deve aceitar uploads multipart e processamento assíncrono.

### RNF-008 — Acessibilidade

Interface compatível com WCAG 2.2 AA.

### RNF-009 — Internacionalização

Estrutura preparada para português brasileiro e inglês.

### RNF-010 — Reprodutibilidade

O verificador deve oferecer builds reproduzíveis em fase posterior.

---

## 21. Segurança e privacidade

### 21.1 Criptografia

- TLS em trânsito.
- Criptografia no storage.
- Chaves de servidor em KMS ou HSM.
- Segredos fora do código-fonte.

### 21.2 Controle de acesso

- RBAC para organizações.
- URLs de download com expiração.
- MFA para administradores.
- Logs de acesso.

Na POC local pode existir uma identidade de desenvolvimento. Qualquer ambiente acessível pela internet deve exigir autenticação mínima e impedir enumeração de sessões, mesmo antes do RBAC institucional.

A primeira autenticação pública usa magic link por e-mail.

### 21.3 Dados sensíveis

A plataforma deve alertar que capturas podem conter:

- dados pessoais;
- conversas privadas;
- informações de crianças e adolescentes;
- dados de saúde;
- dados financeiros;
- segredos empresariais.

### 21.4 LGPD

O produto deve definir claramente:

- controlador e operador em cada modalidade;
- base legal;
- finalidade;
- prazo de retenção;
- procedimentos de acesso;
- política de descarte;
- incidentes de segurança;
- tratamento de solicitações dos titulares.

A retenção imutável deve ser configurada com cuidado, pois pode entrar em tensão com pedidos de eliminação. A arquitetura jurídica precisa distinguir evidências mantidas por obrigação, exercício regular de direitos ou outras bases aplicáveis.

Testes de Object Lock da POC devem usar conteúdo sintético ou público, bucket separado e o menor prazo de retenção aceito pelo provedor. Dados pessoais reais não devem ser usados para validar retenção irreversível.

A POC não aceita dados reais de crianças, saúde ou finanças. Esses usos dependem de política específica e revisão jurídica.

### 21.5 Telemetria

Telemetria deve ser mínima e separada do conteúdo capturado.

---

## 22. Experiência do usuário

### 22.1 Tela inicial

- Nova captura.
- Minhas capturas.
- Verificar pacote.
- Configurações.

### 22.2 Antes da captura

Mostrar:

- o que será coletado;
- o que não será provado;
- o prazo de retenção;
- riscos de capturar conteúdo de terceiros;
- recomendação de navegar mostrando contexto.

### 22.3 Durante a captura

Mostrar:

- indicador visível de gravação;
- duração;
- status de upload;
- quantidade de blocos enviados;
- alertas de conexão;
- botão de screenshot adicional;
- botão de marcador de evento;
- botão de finalizar.

### 22.4 Após a captura

Mostrar:

- status da integridade;
- status do timestamp;
- status da blockchain;
- hash do pacote;
- botão de download;
- relatório;
- limitações.

---

## 23. Relatório de verificação

O relatório deve apresentar:

### Resultado geral

- íntegro;
- íntegro, mas incompleto;
- inválido;
- não verificável.

### Verificações

- estrutura do pacote;
- hashes;
- cadeia;
- assinaturas;
- recibos;
- timestamp;
- Merkle;
- OpenTimestamps;
- retenção declarada;
- versão do software;
- completude e procedência de cada artefato;
- horários do cliente, servidor, TSA e blockchain apresentados separadamente.

### Linguagem recomendada

Usar:

- “hash válido”;
- “assinatura válida”;
- “arquivo não sofreu alteração em relação ao manifesto”;
- “prova temporal válida”;
- “inclusão na raiz Merkle confirmada”;
- “o hash existia até o momento demonstrado pela prova temporal”.

Evitar:

- “conteúdo verdadeiro”;
- “autoria comprovada”;
- “prova definitiva”;
- “validade jurídica garantida”.

---

## 24. Critérios de aceite

### 24.1 POC funcional

A POC será considerada funcional quando:

1. Uma pessoa instalar a extensão.
2. Iniciar uma sessão.
3. Capturar uma página durante pelo menos 60 segundos.
4. Gerar ao menos um vídeo, um screenshot e um arquivo de metadados.
5. Calcular hashes no cliente.
6. Enviar artefatos em blocos.
7. Receber recibos assinados.
8. Interromper e retomar ao menos um upload sem duplicação.
9. Assinar `capture_close` no cliente.
10. Gerar e assinar o manifesto de captura no servidor.
11. Baixar o pacote.
12. Validá-lo integralmente com uma CLI offline.
13. Detectar alteração de um único byte em qualquer artefato.
14. Detectar remoção, duplicação ou troca de ordem de um evento.
15. Identificar explicitamente artefatos indisponíveis ou incompletos.
16. Produzir relatório HTML.
17. Produzir os mesmos hashes e assinaturas dos vetores de teste em TypeScript, Python e Rust.

### 24.2 POC probatória completa

A POC probatória estará completa quando, além dos critérios anteriores:

1. Obtiver carimbo RFC 3161 sobre o manifesto assinado.
2. Gerar attestation válida sem alterar o manifesto.
3. Gerar prova OpenTimestamps, mesmo que inicialmente pendente de confirmação.
4. Gerar complemento assinado após atualização da prova.
5. Armazenar uma cópia de teste em bucket com Object Lock.
6. Validar timestamp, Merkle, OpenTimestamps e attestations na CLI offline.
7. Manter o pacote funcional verificável durante indisponibilidade dos serviços externos.

---

## 25. Testes

### 25.1 Integridade

- Alterar um byte do vídeo.
- Substituir um screenshot.
- Remover uma entrada do JSONL.
- Reordenar eventos.
- Duplicar bloco.
- Alterar manifesto.

Resultado esperado: falha explícita e localizada.

### 25.2 Assinaturas

- Usar chave pública errada.
- Alterar assinatura.
- Alterar conteúdo assinado.
- Usar `key_id`, algoritmo ou prefixo de domínio incorreto.
- Validar vetores idênticos nas três linguagens.

### 25.3 Timestamp

- Certificado fora da validade no `genTime`.
- Estado de revogação ou cadeia de confiança não verificável.
- Certificado não confiável.
- Hash divergente.
- Cadeia incompleta.

### 25.4 Blockchain

- Prova `.ots` inválida.
- Merkle proof incorreta.
- Raiz diferente.
- Confirmação pendente.

### 25.5 Rede

- Queda de conexão.
- Retomada de upload.
- Duplicação de requisição.
- Reenvio idempotente.
- Mesma sequência com conteúdo divergente.
- Encerramento com partes ausentes.
- Reinício do cliente com recuperação do buffer local.
- Reinício do servidor durante finalização.

### 25.6 Storage

- Tentativa de sobrescrita.
- Tentativa de exclusão antes da retenção.
- Teste de versionamento.

### 25.7 Pacotes hostis

- Path traversal e caminhos absolutos.
- Links simbólicos.
- Nomes duplicados.
- ZIP bomb e tamanho descompactado excessivo.
- JSON excessivamente profundo.
- Schema ou algoritmo desconhecido.
- Arquivos extras e arquivos obrigatórios ausentes.

### 25.8 Relógios e completude

- Relógio do cliente incorreto.
- Reinício do tempo monotônico.
- Artefato indisponível.
- Captura parcial de iframe, canvas ou conteúdo protegido.
- Divergência entre horário do cliente, servidor e TSA.

---

## 26. Stack sugerida para a POC

### Extensão

- TypeScript.
- Manifest V3.
- Vite.
- React.
- Web Crypto API.
- MediaRecorder.
- IndexedDB.

### Backend

- Python 3.13.
- FastAPI.
- Pydantic.
- SQLAlchemy.
- PostgreSQL.
- jobs persistidos no PostgreSQL na primeira versão;
- Redis e worker dedicado apenas quando carga ou isolamento justificarem.

### Storage

- Garage para desenvolvimento e Ceph RGW Squid `19.2.5` self-hosted na etapa
  probatória e em produção.
- Object Lock em modo `COMPLIANCE`, versionamento e SSE-KMS com OpenBao/Vault
  como backend do RGW.
- O cluster Ceph é externo ao Railway e operado separadamente da aplicação.

### Criptografia

- SHA-256.
- Ed25519.
- JSON Canonicalization Scheme.

### Timestamp

- Cliente RFC 3161.
- Autoridade externa configurável.

### Blockchain

- OpenTimestamps.
- Agregador Merkle próprio ou biblioteca consolidada.

### Verificador

- Rust.
- Clap para CLI.
- Serde.
- WebAssembly em fase posterior.

### Infraestrutura

- Docker Compose para desenvolvimento.
- `nix develop` como entrada padrão do ambiente local.
- especificações declarativas `cephadm` para o Ceph RGW.
- GitHub Actions para CI.
- SBOM por release.
- Assinatura de builds.

### Produção

- Railway para API, workers e serviços auxiliares.
- PostgreSQL gerenciado com backups e migrações controladas.
- Redis apenas se adotado pelo processamento assíncrono.
- Ceph RGW externo com Object Lock para evidências; volumes locais do Railway não são armazenamento probatório.
- TSA e OpenTimestamps como integrações externas.
- Variáveis de ambiente e secret store para configuração; nenhum segredo no repositório.

---

## 27. Estrutura de repositório

```text
/chitaozinho
├── apps/
│   ├── extension/
│   ├── api/
│   ├── verifier-cli/
│   └── verifier-web/
├── packages/
│   ├── schemas/
│   ├── crypto/
│   ├── canonical-json/
│   └── evidence-format/
├── infra/
│   ├── docker/
│   ├── ceph/
│   ├── railway/
│   └── monitoring/
├── docs/
│   ├── threat-model.md
│   ├── evidence-format.md
│   ├── legal-limitations.md
│   └── verification.md
├── test-vectors/
├── SPEC.md
├── LICENSE
└── README.md
```

---

## 28. Roadmap

### Fase 0 — Prova criptográfica mínima

- Schemas versionados.
- JSON canônico.
- Vetores de teste entre linguagens.
- CLI para empacotar arquivos.
- Manifesto de captura.
- SHA-256.
- Assinatura local.
- Verificador.

### Fase 1 — Captura web

- Extensão Chromium.
- Screenshots.
- Vídeo.
- Metadados.
- Upload em blocos.
- Recibos.
- Retomada e idempotência.
- Pacote funcional e relatório HTML.

### Fase 2 — Prova temporal e preservação

- Object Lock.
- RFC 3161.
- Attestations e complementos.
- Merkle e OpenTimestamps.
- Testes de falha dos serviços externos.

### Fase 3 — Produção e robustez

- Gestão de usuários.
- RBAC, MFA e multi-organização.
- Retenção configurável.
- Relatório PDF.
- Observabilidade e recuperação.
- Agente desktop.
- Hardware-backed keys.
- Atestação.
- Builds reproduzíveis.
- Auditoria externa.

### Fase 4 — Ecossistema jurídico

- Integrações com escritórios.
- Fluxos de cadeia de custódia.
- Exportação pericial.
- Parcerias com notários e entidades certificadoras.

---

## 29. Decisões complementares aprovadas

- Nome público “Chitãozinho”, com identificadores `chitaozinho` e `CHITAOZINHO`.
- `protocol_version` e `schema_version` iniciais em `0.1.0`.
- Pacote ZIP com ZIP64 automático quando necessário.
- React, TypeScript e Vite na extensão.
- Web Crypto nativa, com biblioteca consolidada permitida apenas para hash incremental ou fallback necessário.
- Identidade local no desenvolvimento e magic link por e-mail antes de exposição pública.
- Extensão unpacked na POC; versão, commit e hash do build registrados no manifesto.
- `chrome.debugger` fora da POC.
- Canvas e WebGL cobertos visualmente; iframes em best-effort; DRM e conteúdo protegido marcados como indisponíveis.
- Qualquer TSA RFC 3161 confiável pode ser usada na POC; opções brasileiras devem ser comparadas antes de produção.
- Trust store da TSA explícito e versionado, com atualizações assinadas.
- Garage local e Ceph RGW Squid `19.2.5` self-hosted com Object Lock. A imagem
  OCI é fixada por digest; o RGW usa OpenBao/Vault para SSE-KMS.
- Retenção mínima no teste, 90 dias no gratuito, 5 anos no individual e configurável no institucional.
- Chave raiz offline; chaves operacionais montadas por secret store self-hosted
  ou protegidas por KMS/HSM equivalente, rotacionadas a cada 90 dias, com
  revogações assinadas.
- Calendários públicos OpenTimestamps; agregação a cada hora ou 100 sessões.
- POC restrita a conteúdo público ou sintético. LGPD, dados sensíveis e legal hold exigem revisão jurídica antes de produção.
- Formato, schemas, verificador, componentes e histórico de chaves públicos.
- Staging no Railway primeiro; produção somente após POC probatória, revisão de segurança e autorização explícita.

---

## 30. Decisões técnicas aprovadas

1. Começar com extensão Chromium, sem aplicativo desktop.
2. Usar SHA-256 e Ed25519.
3. Gravar vídeo em WebM sem recompressão no backend.
4. Usar JSON canônico para assinaturas.
5. Emitir recibos do servidor a cada lote de blocos.
6. Separar manifesto de captura, attestations e hash externo do ZIP.
7. Agregar sessões em árvore de Merkle.
8. Usar OpenTimestamps, sem contrato inteligente e sem token.
9. Carimbar o manifesto assinado sem incorporar o resultado no próprio manifesto.
10. Publicar o formato do pacote e o verificador como open source.
11. Tratar blockchain como camada adicional, não como fonte única de confiança.
12. Nunca afirmar que o sistema comprova autoria ou veracidade material.
13. Usar chave efêmera por sessão para o cliente na POC.
14. Armazenar evidências finais em Ceph RGW Object Lock somente na etapa probatória e de produção.
15. Usar Railway para serviços, nunca como storage probatório.

---

## 31. Definição de pronto

Uma funcionalidade é considerada pronta quando:

- possui testes automatizados;
- tem documentação;
- produz logs auditáveis;
- não altera arquivos originais;
- possui tratamento explícito de falhas;
- informa suas limitações ao usuário;
- gera artefatos verificáveis pelo CLI;
- passa por revisão de segurança;
- não publica dados pessoais em blockchain;
- mantém compatibilidade com o schema versionado;
- passa pelos vetores de teste compartilhados quando altera protocolo, schema ou criptografia.

---

## 32. Licença

Verificador, schemas, formato do pacote, extensão e backend usam Apache-2.0.

O código-fonte, o verificador e a especificação do formato permanecem abertos mesmo em um modelo comercial.

---

## 33. Resumo executivo da POC

A POC funcional deve permitir que uma pessoa:

1. instale uma extensão Chromium;
2. inicie uma sessão de captura;
3. grave uma aba e gere screenshots;
4. registre metadados e sequência de eventos;
5. identifique artefatos incompletos ou indisponíveis;
6. calcule hashes no próprio navegador;
7. envie os dados ao servidor em blocos com retomada;
8. receba recibos assinados;
9. assine o encerramento da captura;
10. gere um manifesto de captura assinado pelo servidor;
11. baixe um pacote ZIP;
12. verifique esse pacote offline e detecte adulterações.

A etapa probatória completa adiciona RFC 3161, attestations, Merkle,
OpenTimestamps e teste de Object Lock sem alterar o manifesto ou o pacote
original. A produção executa API e workers no Railway e mantém as evidências em
Ceph RGW self-hosted, externo ao Railway, com retenção apropriada.

O produto deve provar integridade, continuidade de coleta e existência temporal dos bytes registrados, sem prometer comprovação automática de autoria, veracidade ou validade jurídica definitiva.
