export function Privacy() {
  return (
    <main id="main-content" className="privacy-page" tabIndex={-1}>
      <p className="eyebrow">Seus dados, com clareza</p>
      <h1>Política de privacidade</h1>
      <p>Atualizada em 18 de setembro de 2026.</p>

      <h2>O essencial</h2>
      <p>
        O Evidências é uma ferramenta da Conectas Direitos Humanos para
        registrar conteúdos da internet e compartilhar registros verificáveis.
        Na versão atual, os arquivos capturados ficam no seu dispositivo. O
        servidor recebe seu e-mail, hashes e informações técnicas necessárias ao
        serviço — não uma cópia dos conteúdos capturados.
      </p>
      <p>
        Um hash é um resumo criptográfico usado para conferir se um arquivo
        mudou. Ele não é uma cópia do arquivo, mas pode ser um dado pessoal
        quando estiver associado a uma pessoa.
      </p>

      <h2>Quem cuida dos dados</h2>
      <p>
        A Conectas Direitos Humanos (Associação Direitos Humanos em Rede) é a
        responsável pelo tratamento dos dados do serviço. Para dúvidas ou
        pedidos sobre seus dados, escreva para{" "}
        <a href="mailto:contato@evidencias.org.br">contato@evidencias.org.br</a>
        .
      </p>

      <h2>O que usamos e por quê</h2>
      <ul>
        <li>
          E-mail e dados de autenticação: criar sua conta e permitir o acesso
          por link, sem pedir a senha do seu e-mail.
        </li>
        <li>
          IP e registros de segurança: limitar pedidos de acesso e combater
          abuso. O controle de pedidos guarda um hash do IP.
        </li>
        <li>
          Hashes, identificadores, horários e dados técnicos: organizar
          registros e emitir assinaturas e comprovantes de tempo.
        </li>
        <li>
          Conteúdo da aba escolhida: texto, HTML, imagens, áudio, vídeo,
          endereço, título e eventos de rolagem e navegação durante a captura.
          No modo atual, os conteúdos e seu contexto são mantidos localmente.
        </li>
      </ul>
      <p>
        A captura começa por uma ação sua. Não lemos todo o histórico do
        navegador nem usamos GPS. Evite registrar informações desnecessárias.
        Uma página pode conter conversas ou dados sensíveis de outras pessoas;
        usar a ferramenta não autoriza, por si só, a coleta ou divulgação desses
        dados.
      </p>

      <h2>Onde ficam os arquivos</h2>
      <p>
        Guarde o ZIP em um lugar seguro: não temos uma cópia para recuperá-lo.
        Remover a extensão ou limpar os dados do navegador pode apagar registros
        locais, mas não apaga os ZIPs já baixados. Você controla essas cópias.
      </p>
      <p>
        O verificador confere os arquivos no navegador, sem enviá-los ao
        servidor. A visita ao site gera as conexões necessárias para carregar a
        página. Se você compartilhar um ZIP, o destinatário terá acesso ao
        conteúdo dele.
      </p>

      <h2>Fornecedores e comprovantes públicos</h2>
      <p>
        Usamos Railway para hospedagem e Resend para enviar links de acesso. O
        Resend recebe o e-mail e a mensagem necessários ao envio. Esses serviços
        podem tratar dados fora do Brasil; as transferências devem seguir as
        garantias exigidas pela LGPD. Você pode pedir informações sobre elas
        pelo nosso contato de privacidade.
      </p>
      <p>
        Calendários públicos OpenTimestamps recebem resumos criptográficos para
        produzir provas de tempo. O processo pode resultar em um registro no
        Bitcoin. Não publicamos seu e-mail ou os arquivos capturados na
        blockchain. Registros confirmados nela não podem ser apagados por nós.
      </p>
      <p>
        Não vendemos dados, não os usamos para publicidade direcionada nem para
        análise de crédito. O uso e a transferência de dados se limitam à
        finalidade da ferramenta e às hipóteses permitidas pelas regras de Uso
        Limitado da Chrome Web Store, como a operação do serviço, segurança e
        obrigações legais.
      </p>

      <h2>Por quanto tempo</h2>
      <ul>
        <li>Conta: até você pedir sua exclusão.</li>
        <li>
          Hashes e comprovantes no servidor: 12 meses a partir do registro.
        </li>
        <li>
          Registros de segurança no banco da aplicação: 30 dias a partir do
          evento.
        </li>
        <li>Arquivos no dispositivo: até você apagá-los.</li>
      </ul>
      <p className="privacy-status">
        Uma rotina diária remove os registros vencidos. A remoção pode ocorrer
        na execução seguinte ao término do prazo; falhas são registradas para
        nova tentativa. Pedidos de exclusão de conta são atendidos pelo contato
        de privacidade, após confirmação de identidade. Um ponto criptográfico,
        sem o conteúdo dos eventos antigos, mantém a continuidade da auditoria.
      </p>
      <p>
        Cópias de segurança e registros operacionais dos fornecedores têm ciclos
        próprios de retenção e podem persistir temporariamente após a exclusão
        na aplicação, com acesso restrito. A limpeza deve ser reaplicada antes
        de colocar uma cópia restaurada em uso. Você pode solicitar detalhes
        desses prazos pelo contato de privacidade.
      </p>
      <p>
        Uma obrigação legal ou o exercício regular de direitos pode exigir a
        conservação de dados específicos por mais tempo; nesse caso,
        explicaremos o motivo. A exclusão no serviço não remove cópias que você
        compartilhou nem compromissos criptográficos já confirmados no Bitcoin.
      </p>

      <h2>Por que podemos tratar esses dados</h2>
      <p>
        Usamos os dados necessários para prestar o serviço solicitado por você
        (execução da relação contratual, art. 7º, V, da LGPD). Para prevenção de
        abuso, consideramos o legítimo interesse, respeitando seus direitos e
        limitando o tratamento ao necessário (art. 7º, IX). Obrigações legais e
        exercício regular de direitos podem justificar tratamentos específicos.
        Essas bases não autorizam indiscriminadamente o uso de dados sensíveis
        ou de terceiros. Quando for necessário consentimento, ele deve ser
        solicitado de forma específica, não presumido pela leitura desta
        política.
      </p>

      <h2>Seus direitos</h2>
      <p>
        Você pode pedir confirmação do tratamento, acesso, correção, informações
        sobre compartilhamento e, nos casos previstos na LGPD, exclusão,
        anonimização, bloqueio e portabilidade. Também pode retirar
        consentimento quando essa for a base do tratamento, opor-se a tratamento
        irregular e apresentar uma petição à ANPD.
      </p>
      <p>
        O pedido é gratuito. Podemos precisar confirmar sua identidade com o
        mínimo de informações necessário. Se algum dado precisar ser mantido por
        motivo legal, explicaremos a razão. Escreva para{" "}
        <a href="mailto:contato@evidencias.org.br">contato@evidencias.org.br</a>
        .
      </p>

      <h2>Segurança e mudanças</h2>
      <p>
        Usamos HTTPS e controles de autenticação e acesso. Nenhum sistema é
        livre de risco: proteja seu dispositivo e os pacotes baixados. Mudanças
        relevantes nesta política serão informadas de forma clara.
      </p>
      <p>
        Referências:{" "}
        <a href="https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm">
          LGPD
        </a>{" "}
        e{" "}
        <a href="https://developer.chrome.com/docs/webstore/program-policies/user-data-faq">
          regras de dados da Chrome Web Store
        </a>
        .
      </p>
    </main>
  );
}
