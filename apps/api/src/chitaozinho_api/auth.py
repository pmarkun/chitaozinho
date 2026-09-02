from __future__ import annotations

import hashlib
import json
import re
import secrets
import smtplib
import ssl
import uuid
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .config import Settings
from .models import AccessToken, MagicLinkRequestAttempt, MagicLinkToken, User

COOKIE_NAME = "chitaozinho_session"
CONSUME_HTML = """<!doctype html>
<html lang="pt-BR">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Acesso ao Chitãozinho</title>
<body>
<main>
  <h1>Acesso ao Chitãozinho</h1>
  <p id="status">Validando link…</p>
</main>
<script>
const status = document.querySelector("#status");
const token = location.hash.slice(1);
history.replaceState(null, "", location.pathname);
if (!token) {
  status.textContent = "Link inválido.";
} else {
  fetch("/v1/auth/magic-links/exchange", {
    method: "POST",
    credentials: "include",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({token})
  }).then((response) => {
    status.textContent = response.ok
      ? "Acesso confirmado. Você pode fechar esta aba e voltar à extensão."
      : "Este link é inválido ou expirou.";
  }).catch(() => {
    status.textContent = "Não foi possível confirmar o acesso.";
  });
}
</script>
</body>
</html>
"""


class MagicLinkSender(Protocol):
    def __call__(self, email: str, link: str) -> None: ...


class RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if (
        len(normalized) > 320
        or re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized) is None
    ):
        raise ValueError("invalid email address")
    return normalized


def create_magic_link(
    database: Session,
    settings: Settings,
    email: str,
) -> tuple[str, str]:
    normalized = normalize_email(email)
    user = database.scalar(select(User).where(User.email == normalized))
    now = datetime.now(UTC)
    if user is None:
        user = User(id=uuid.uuid4().hex, email=normalized, created_at=now)
        database.add(user)
        database.flush()
    token = secrets.token_urlsafe(32)
    database.add(
        MagicLinkToken(
            id=uuid.uuid4().hex,
            user_id=user.id,
            token_hash=token_hash(settings, token),
            expires_at=now + timedelta(seconds=settings.magic_link_ttl_seconds),
            consumed_at=None,
            created_at=now,
        )
    )
    database.flush()
    return user.id, token


def exchange_magic_link(
    database: Session,
    settings: Settings,
    token: str,
) -> tuple[str, str, datetime] | None:
    if len(token) > 256:
        return None
    statement = select(MagicLinkToken).where(
        MagicLinkToken.token_hash == token_hash(settings, token)
    )
    if database.bind is not None and database.bind.dialect.name == "postgresql":
        statement = statement.with_for_update()
    magic_link = database.scalar(statement)
    now = datetime.now(UTC)
    if (
        magic_link is None
        or magic_link.consumed_at is not None
        or aware(magic_link.expires_at) <= now
    ):
        return None
    magic_link.consumed_at = now
    access_token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(seconds=settings.access_token_ttl_seconds)
    database.add(
        AccessToken(
            id=uuid.uuid4().hex,
            user_id=magic_link.user_id,
            token_hash=token_hash(settings, access_token),
            expires_at=expires_at,
            revoked_at=None,
            created_at=now,
        )
    )
    database.flush()
    return magic_link.user_id, access_token, expires_at


def authenticate_access_token(
    database: Session,
    settings: Settings,
    token: str | None,
) -> str | None:
    if token is None or len(token) > 256:
        return None
    access = database.scalar(
        select(AccessToken).where(
            AccessToken.token_hash == token_hash(settings, token)
        )
    )
    if (
        access is None
        or access.revoked_at is not None
        or aware(access.expires_at) <= datetime.now(UTC)
    ):
        return None
    return access.user_id


def register_magic_link_attempt(
    database: Session,
    settings: Settings,
    email: str,
    client_ip: str,
    *,
    now: datetime | None = None,
) -> bool:
    current = now or datetime.now(UTC)
    cutoff = current - timedelta(hours=1)
    normalized = normalize_email(email)
    email_hash = rate_limit_hash(settings, "email", normalized)
    ip_hash = rate_limit_hash(settings, "ip", client_ip or "unknown")
    email_count = database.scalar(
        select(func.count())
        .select_from(MagicLinkRequestAttempt)
        .where(
            MagicLinkRequestAttempt.email_hash == email_hash,
            MagicLinkRequestAttempt.created_at >= cutoff,
        )
    )
    ip_count = database.scalar(
        select(func.count())
        .select_from(MagicLinkRequestAttempt)
        .where(
            MagicLinkRequestAttempt.ip_hash == ip_hash,
            MagicLinkRequestAttempt.created_at >= cutoff,
        )
    )
    database.add(
        MagicLinkRequestAttempt(
            email_hash=email_hash,
            ip_hash=ip_hash,
            created_at=current,
        )
    )
    database.execute(
        delete(MagicLinkRequestAttempt).where(
            MagicLinkRequestAttempt.created_at < current - timedelta(days=1)
        )
    )
    return (
        int(email_count or 0) < settings.magic_link_email_limit_per_hour
        and int(ip_count or 0) < settings.magic_link_ip_limit_per_hour
    )


def smtp_magic_link_sender(settings: Settings) -> MagicLinkSender:
    if settings.smtp_host is None or settings.smtp_from is None:
        raise ValueError("SMTP is not configured")

    def send(email: str, link: str) -> None:
        message = EmailMessage()
        message["Subject"] = "Seu acesso ao Chitãozinho"
        message["From"] = settings.smtp_from
        message["To"] = email
        message.set_content(
            "Abra este link para entrar no Chitãozinho. "
            "Ele expira e só pode ser usado uma vez:\n\n"
            f"{link}\n"
        )
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.ehlo()
            if settings.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            if settings.smtp_username is not None:
                if settings.smtp_password is None:
                    raise ValueError("SMTP password is required with a username")
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)

    return send


def resend_magic_link_sender(settings: Settings) -> MagicLinkSender:
    if settings.resend_api_key is None or settings.resend_from is None:
        raise ValueError("Resend is not configured")
    opener = build_opener(RejectRedirects(), HTTPSHandler(context=ssl.create_default_context()))

    def send(email: str, link: str) -> None:
        payload = {
            "to": [normalize_email(email)],
            "from": settings.resend_from,
            "subject": "Seu acesso ao Chitãozinho",
            "text": (
                "Abra este link para entrar no Chitãozinho. "
                "Ele expira e só pode ser usado uma vez:\n\n"
                f"{link}\n"
            ),
        }
        request = Request(
            "https://api.resend.com/emails",
            data=json.dumps(payload, separators=(",", ":")).encode(),
            method="POST",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
                "User-Agent": "chitaozinho-api/0.1.1",
            },
        )
        try:
            with opener.open(request, timeout=15) as response:
                content = response.read(65_537)
                code = response.status
        except HTTPError as error:
            raise RuntimeError(f"Resend request failed with HTTP {error.code}") from error
        except (OSError, URLError) as error:
            raise RuntimeError("Resend request failed") from error
        if len(content) > 65_536:
            raise RuntimeError("Resend response exceeds the safety limit")
        if not 200 <= code < 300:
            raise RuntimeError(f"Resend request failed with HTTP {code}")

    return send


def magic_link_url(settings: Settings, token: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}/v1/auth/consume#{token}"


def token_hash(settings: Settings, token: str) -> str:
    pepper = settings.auth_token_pepper or ""
    return hashlib.sha256(f"{pepper}\0{token}".encode()).hexdigest()


def rate_limit_hash(settings: Settings, kind: str, value: str) -> str:
    pepper = settings.auth_token_pepper or "development"
    return hashlib.sha256(f"{pepper}\0rate-limit\0{kind}\0{value}".encode()).hexdigest()


def aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
