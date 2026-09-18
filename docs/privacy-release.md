# Publicação da política de privacidade

O usuário confirmou em 18/09/2026 a validação institucional e jurídica, o contato
`contato@evidencias.org.br`, o domínio `evidencias.org.br` e os prazos propostos:
conta até pedido de exclusão; hashes/comprovantes por 12 meses; segurança por
até 30 dias. A página está em `apps/verifier-web/src/privacy.tsx`, rota
`/privacidade`, com link no rodapé. Não é um atestado de adequação integral.

## Rotina diária

O serviço `retention-cleanup`, às 03:15 UTC, executa a expiração legada e depois
`cleanup_personal_data`: remove capturas com 12 meses desde a criação e suas
provas privadas, preservando lotes Merkle ainda compartilhados por outras sessões.
Objetos legados precisam concluir a retenção original antes da remoção dos metadados.
Jobs em execução fazem a remoção falhar para nova tentativa; falhas parciais
mantêm metadados e fazem o cron retornar erro. O relatório contém só contagens.

A auditoria é verificada antes/depois da poda. Um checkpoint guarda somente a
sequência/hash do último evento removido, sem assunto ou conteúdo antigo. Só o
prefixo com mais de 30 dias é removido; eventos retidos não são alterados.
Tokens vencidos são removidos; tentativas de login e jobs finalizados antigos
também são limpos. Os ZIPs já baixados e a blockchain não são alterados.

## Conferir sem apagar e atender pedidos

No backend de staging, `python -m chitaozinho_api.privacy_cleanup` simula a rotina.
Adicione `--apply` para aplicar. Para uma conta:

1. Confirme identidade e pedido pelo canal de atendimento, sem pedir senha.
2. Identifique internamente o ID exato; não copie dados pessoais para logs.
3. Simule `python -m chitaozinho_api.privacy_cleanup --user-id ID_EXATO`.
4. Execute o mesmo comando com `--apply`; confira `failures=0` e as contagens.
5. Explique que cópias locais/compartilhadas e blockchain não são apagadas;
   eventos de segurança podem permanecer até a retenção de 30 dias.
6. Se necessário, solicite remoção antecipada aos fornecedores pelo suporte.

Não há endpoint público destrutivo. Conta que ganhar novas capturas durante o
pedido exige retry. Criação de capturas e remoção da conta usam lock de usuário
para impedir novos registros órfãos após a exclusão.

## Fornecedores, backups e recuperação

O usuário autorizou publicar no Railway sem esperar o DNS do domínio definitivo.
Confirmar DNS, HTTPS e entrega do contato antes de divulgar a URL definitiva.
Esta rotina não altera retenção contratada de logs/backups dos fornecedores.
A política pública distingue esses ciclos. Acompanhar a rotação e limitar acesso
às cópias; o plano original prevê backups diários com sete dias de retenção.
Após restaurar, reaplicar retenção e pedidos de exclusão atendidos antes de
liberar tráfego. Não restaurar dados apagados como forma de rollback.

Referências: [Railway](https://docs.railway.com/observability/logs),
[Resend](https://resend.com/security/gdpr).

## Migração e rollback

`0008_privacy_retention` mantém a proibição de UPDATE na auditoria e só permite
DELETE de eventos antigos cobertos pelo checkpoint. Não desativar triggers nem
editar hashes. A aplicação segue rejeitando edição/exclusão ORM comum.
Depois da primeira poda, não fazer downgrade para código sem suporte a checkpoint:
a migração recusa essa operação. Corrigir para frente ou pausar o cron.
