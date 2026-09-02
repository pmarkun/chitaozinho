# Monitoring

Railway verifica `/readyz`, que testa PostgreSQL e storage antes de liberar
tráfego. Os procedimentos de diagnóstico, recuperação e rollback estão em
[`docs/operations.md`](../../docs/operations.md).

`/metrics` expõe contadores e duração agregada de requisições no formato
Prometheus. Em staging e produção ele exige
`Authorization: Bearer $CHITAOZINHO_METRICS_TOKEN`; o token possui pelo menos
32 caracteres e fica no secret store. O endpoint também expõe contagens
agregadas dos jobs por estado, jobs prontos para processamento e jobs
`running` além do limite de recuperação, sem IDs ou payloads. Os logs HTTP são
JSON e incluem somente `request_id`, método, rota parametrizada, status e
duração; o access log padrão do Uvicorn fica desativado para não registrar URLs
ou queries sensíveis.

O worker emite JSON para início, conclusão e falha de jobs usando apenas
`job_id`, `subject_id`, tipo, estado, tentativas e tipo da exceção. A mensagem
da exceção não é persistida nem registrada, evitando vazar URLs, tokens ou
conteúdo retornado por provedores.

Antes de produção, conecte o endpoint e os logs a um monitor externo e configure
alertas para indisponibilidade de `/readyz`, respostas 5xx e aumento sustentado
de duração. As métricas ficam em memória e reiniciam com cada processo.

[`alerts.rules.json`](alerts.rules.json) contém o contrato versionado de cinco
alertas Prometheus para indisponibilidade, proporção de 5xx, latência, backlog
e jobs abandonados. `scripts/check-monitoring-config.py` valida nomes,
severidades, durações, anotações e ausência de labels de alta cardinalidade.
O monitor publicado ainda precisa importar essas regras e configurar o bearer
token; manter o arquivo no repositório não fecha esse gate externo.
