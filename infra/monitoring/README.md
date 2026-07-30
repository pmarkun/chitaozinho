# Monitoring

Railway verifica `/readyz`, que testa PostgreSQL e storage antes de liberar
tráfego. Os procedimentos de diagnóstico, recuperação e rollback estão em
[`docs/runbooks.md`](../../docs/runbooks.md).

`/metrics` expõe contadores e duração agregada de requisições no formato
Prometheus. Os logs HTTP são JSON e incluem somente `request_id`, método, rota
parametrizada, status e duração; o access log padrão do Uvicorn fica desativado
para não registrar URLs ou queries sensíveis.

Antes de produção, conecte o endpoint e os logs a um monitor externo e configure
alertas para indisponibilidade de `/readyz`, respostas 5xx e aumento sustentado
de duração. As métricas ficam em memória e reiniciam com cada processo.
