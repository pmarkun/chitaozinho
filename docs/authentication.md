# Autenticação

O desenvolvimento local usa `CHITAOZINHO_AUTH_MODE=development`. Ambientes
públicos usam magic link, token pepper, cookies seguros e isolamento por dono.
O beta envia mensagens pela API HTTP do Resend.

## Fluxo público

1. A extensão solicita um link para um endereço de e-mail.
2. A API armazena somente o SHA-256 do token aleatório de uso único.
3. O token segue no fragmento `#` da URL e não chega aos access logs HTTP.
4. A página de consumo troca o token uma vez por uma sessão aleatória.
5. A sessão é armazenada como hash e entregue em cookie
   `HttpOnly; Secure; SameSite=None` com expiração.
6. Requisições que mudam estado exigem a origem exata da extensão.
7. Sessões, jobs e downloads permanecem restritos ao dono autenticado.

A resposta à solicitação do magic link é uniforme, exista ou não uma conta. Os
limites persistentes são de cinco solicitações por e-mail e vinte por IP a cada
hora.

## Envio de e-mail

O beta configura:

```text
CHITAOZINHO_EMAIL_PROVIDER=resend
CHITAOZINHO_RESEND_API_KEY=...
CHITAOZINHO_RESEND_FROM=Chitãozinho <acesso@mail.arapy.ia.br>
```

O domínio `mail.arapy.ia.br` precisa aparecer como verificado no Resend. A
chave deve possuir apenas a permissão necessária para envio e deve ficar no
secret store do Railway. A integração limita a resposta, não segue redirects,
usa timeout e falha fechada.

O código ainda aceita SMTP explicitamente configurado para desenvolvimento ou
instalações compatíveis. Fora do ambiente local, SMTP exige STARTTLS, host e
remetente. O Railway beta não usa esse caminho.

## Downloads

Downloads de pacotes usam uma URL bearer separada e de curta duração. O HMAC
vincula o ID opaco da sessão e a expiração. Endpoints recusam tokens ausentes,
alterados, expirados ou emitidos para outra sessão e respondem com
`Cache-Control: private, no-store`. O prazo padrão é cinco minutos e pode ser
configurado, até uma hora, por `CHITAOZINHO_DOWNLOAD_URL_TTL_SECONDS`.

## CORS e privacidade

Staging e produção exigem `CHITAOZINHO_EXTENSION_IDS` com IDs Chromium exatos
de 32 caracteres. A API deriva daí a allowlist CORS.
`CHITAOZINHO_CORS_ORIGIN_REGEX` é apenas uma conveniência local e não pode
ampliar um deploy público.

Eventos de auditoria usam um identificador opaco de usuário. E-mail, tokens,
cookies, credenciais do Resend e credenciais SMTP não entram em eventos ou
logs.
