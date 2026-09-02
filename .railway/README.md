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
segredos do processador OpenTimestamps.
