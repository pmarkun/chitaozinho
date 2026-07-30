# Authentication

Local development uses `CHITAOZINHO_AUTH_MODE=development`. Any non-local
environment fails startup unless magic-link authentication, a token pepper and
SMTP are configured.

Public authentication works as follows:

1. the extension requests a link for an email address;
2. only a SHA-256 hash of the random one-time token is stored;
3. the email URL carries the token after `#`, so HTTP access logs never receive
   it;
4. the same-origin consume page exchanges it once for a random access session;
5. the access session is stored as a hash and delivered in an expiring
   `HttpOnly; Secure; SameSite=None` cookie;
6. state-changing cookie requests require the configured extension origin, and
   sessions and jobs are scoped to their owner.

Audit events use an opaque user ID and never include email, token, cookie or
SMTP credentials. The extension sends requests with browser credentials and
detects successful authentication after the user returns from the email link.

SMTP uses STARTTLS outside local development. Provider credentials belong only
in the Railway secret store or an equivalent local secret source.
