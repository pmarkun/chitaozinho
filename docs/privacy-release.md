# Publicação da política de privacidade

O usuário confirmou em 18/09/2026 a validação institucional e jurídica, o contato
`contato@evidencias.org.br`, o domínio `evidencias.org.br` e os prazos propostos:
conta até pedido de exclusão; hashes/comprovantes por 12 meses; segurança por
até 30 dias. A página está em `apps/verifier-web/src/privacy.tsx`, rota
`/privacidade`, com link no rodapé. Não é um atestado de adequação integral.

## Bloqueios técnicos de publicação definitiva

- A consulta local de `https://evidencias.org.br` retornou falha de resolução
  de DNS. Confirmar domínio, HTTPS e entrega do contato antes de divulgar a URL.
- A limpeza atual de objetos não implementa a retenção geral de dados pessoais.
  A página informa explicitamente que os novos prazos ainda não são automáticos.
- `AuditEvent` é append-only (`models.py`); não contornar a proteção com SQL bruto.
  Projetar minimização/pseudonimização, retenção, pedidos de exclusão e testes sem
  invalidar comprovantes ou apagar raízes compartilhadas de lotes ainda necessários.
- Verificar logs de plataforma e OpenBao, tokens vencidos, backups e dados legados.
  Uma política de banco não altera automaticamente a retenção dos fornecedores.

Não houve migração, exclusão de dados, alteração de DNS, credenciais ou deploy
como parte desta preparação. A validação jurídica informada pelo usuário não
substitui a verificação técnica dos comportamentos prometidos.
