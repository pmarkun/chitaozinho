# Configuração Railway

[`railway.ts`](railway.ts) é a única fonte declarativa da topologia de staging:
serviços, funções agendadas, PostgreSQL, Bucket, volume, domínios, limites e
referências de variáveis.

```sh
railway config plan
railway config apply
```

`plan` é somente leitura. Revise o conjunto completo antes de aplicar; mudanças
destrutivas exigem autorização operacional separada. Segredos importados usam
`preserve()` ou referências entre serviços e nunca devem ser escritos no
arquivo.

Valide o contrato localmente com:

```sh
nix develop --command python scripts/check-railway-config.py
```

O validador protege a separação de processos, cron schedules, healthchecks,
limites de memória, rede privada do OpenBao, volume exclusivo e referências de
segredos do processador OpenTimestamps. Os `watchPatterns` limitam rebuilds aos
arquivos usados por cada imagem; em especial, mudanças apenas na API ou na
documentação não reiniciam o OpenBao.

O OpenBao responde ao healthcheck interno em `/healthz` pela porta `$PORT`. O
probe só retorna `200` quando `/v1/sys/health` confirma que o cofre está
inicializado e desbloqueado. Em um deploy legítimo do OpenBao, o Railway aguarda
até dez minutos para o desbloqueio manual antes de rejeitar a nova versão.
