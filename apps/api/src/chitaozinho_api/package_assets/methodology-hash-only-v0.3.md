# Evidências — guarda local e registro de hashes (v0.3)

Este pacote foi montado no dispositivo de captura. Imagens, vídeo, DOM, texto,
URL e título não são enviados ao serviço. O coletor deve guardar o ZIP original
e seu checksum; não existe cópia remota dos arquivos para recuperação.

O cliente calcula hashes SHA-256, encadeia os eventos e os assina com uma chave
da sessão. Os detalhes dos eventos ficam em `capture/context.json`; o servidor
recebe seus compromissos criptográficos e metadados técnicos (sequência,
tamanho declarado, identificadores, horários declarados e versão do software).

Recibos `0.2.0` com `hash_registered` atestam o registro do hash declarado.
O servidor verifica a assinatura e a sequência, mas não recalcula o hash dos
arquivos originais, pois não os recebe. Esses recibos não atestam custódia,
armazenamento, imutabilidade ou veracidade do conteúdo.

O manifesto e o índice são assinados pelo serviço. Ao montar e verificar o ZIP,
o cliente/verificador recalcula os hashes dos arquivos locais e confere seu
vínculo com os documentos assinados. O verificador também confere a cadeia e
a declaração de encerramento. A identidade do signatário depende de obter uma
chave ou raiz de confiança por canal independente.

OpenTimestamps registra o hash do manifesto por lotes, sem publicar conteúdo.
Uma submissão pendente não comprova confirmação no Bitcoin. Complementos
temporais são obtidos separadamente; não alteram este ZIP. O horário de um
recibo é uma declaração do serviço, não um carimbo externo já confirmado.

O modo remoto opcional usa recibos legados de persistência; ele não se aplica
a este pacote. Dados de autenticação e registros técnicos do serviço continuam
existindo e exigem política própria de acesso e retenção.
