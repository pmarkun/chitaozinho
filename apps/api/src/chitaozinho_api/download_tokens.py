from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta

from .config import Settings


def create_download_token(
    settings: Settings,
    session_id: str,
    *,
    now: datetime | None = None,
) -> tuple[str, datetime]:
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(seconds=settings.download_url_ttl_seconds)
    payload = {
        "expires_at": int(expires_at.timestamp()),
        "nonce": secrets.token_urlsafe(16),
        "session_id": session_id,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ).rstrip(b"=")
    signature = hmac.new(download_secret(settings), encoded, hashlib.sha256).hexdigest()
    return f"{encoded.decode()}.{signature}", expires_at


def verify_download_token(
    settings: Settings,
    token: str | None,
    session_id: str,
    *,
    now: datetime | None = None,
) -> bool:
    if token is None or len(token) > 1024:
        return False
    try:
        encoded_text, supplied_signature = token.split(".", 1)
        encoded = encoded_text.encode("ascii")
        expected_signature = hmac.new(
            download_secret(settings),
            encoded,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return False
        padding = b"=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding))
    except (UnicodeEncodeError, ValueError, json.JSONDecodeError):
        return False
    current = now or datetime.now(UTC)
    return (
        set(payload) == {"expires_at", "nonce", "session_id"}
        and payload["session_id"] == session_id
        and isinstance(payload["expires_at"], int)
        and payload["expires_at"] >= int(current.timestamp())
        and isinstance(payload["nonce"], str)
        and bool(payload["nonce"])
    )


def download_secret(settings: Settings) -> bytes:
    configured = settings.auth_token_pepper or settings.server_seed_hex
    if configured is None:
        raise RuntimeError("download token secret is not configured")
    return hashlib.sha256(f"chitaozinho-download-v1\0{configured}".encode()).digest()
