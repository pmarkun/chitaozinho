from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from chitaozinho_api.config import Settings
from chitaozinho_api.main import create_app
from chitaozinho_api.models import AccessToken, AuditEvent, MagicLinkToken, User
from fastapi.testclient import TestClient
from sqlalchemy import select

SERVER_SEED = "11" * 32


def test_magic_link_is_single_use_and_creates_an_authorized_cookie(
    tmp_path: Path,
) -> None:
    delivered: list[tuple[str, str]] = []
    settings = auth_settings(tmp_path)
    client = TestClient(
        create_app(
            settings,
            magic_link_sender=lambda email, link: delivered.append((email, link)),
            create_tables=True,
        )
    )

    assert client.post("/v1/sessions").status_code == 401
    assert client.get("/v1/auth/session").json() == {"authenticated": False}
    requested = client.post(
        "/v1/auth/magic-links",
        json={"email": "  Person@Example.COM "},
    )
    assert requested.status_code == 202
    assert requested.content == b""
    assert delivered[0][0] == "person@example.com"
    link = delivered[0][1]
    assert "/v1/auth/consume#" in link
    assert "?" not in link
    token = link.split("#", 1)[1]

    page = client.get("/v1/auth/consume")
    assert page.status_code == 200
    assert token not in page.text
    assert page.headers["cache-control"] == "no-store"
    assert page.headers["referrer-policy"] == "no-referrer"

    exchanged = client.post(
        "/v1/auth/magic-links/exchange",
        json={"token": token},
    )
    assert exchanged.status_code == 204
    cookie = exchanged.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=none" in cookie
    assert client.get("/v1/auth/session").json() == {"authenticated": True}
    created = client.post(
        "/v1/sessions",
        headers={
            "Origin": "chrome-extension://abcdefghijklmnopabcdefghijklmnop"
        },
    )
    assert created.status_code == 201
    assert client.post("/v1/sessions").status_code == 403
    assert (
        client.post(
            "/v1/auth/magic-links/exchange",
            json={"token": token},
        ).status_code
        == 401
    )

    with client.app.state.session_factory() as database:
        user = database.scalar(select(User))
        assert user is not None
        assert user.email == "person@example.com"
        magic = database.scalar(select(MagicLinkToken))
        access = database.scalar(select(AccessToken))
        assert magic is not None and access is not None
        assert magic.token_hash != token
        assert access.token_hash != client.cookies.get("chitaozinho_session")
        events = list(database.scalars(select(AuditEvent)))
        assert all("email" not in event.details for event in events)

    other_links: list[str] = []
    other = TestClient(client.app)
    assert (
        other.post(
            "/v1/auth/magic-links",
            json={"email": "other@example.com"},
        ).status_code
        == 202
    )
    other_links.append(delivered[-1][1])
    other_token = other_links[0].split("#", 1)[1]
    assert (
        other.post(
            "/v1/auth/magic-links/exchange",
            json={"token": other_token},
        ).status_code
        == 204
    )
    assert (
        other.get(f"/v1/sessions/{created.json()['session_id']}").status_code
        == 404
    )


def test_expired_magic_link_and_delivery_failure_fail_closed(
    tmp_path: Path,
) -> None:
    delivered: list[str] = []
    settings = auth_settings(tmp_path)
    app = create_app(
        settings,
        magic_link_sender=lambda _email, link: delivered.append(link),
        create_tables=True,
    )
    client = TestClient(app)
    assert (
        client.post(
            "/v1/auth/magic-links",
            json={"email": "person@example.com"},
        ).status_code
        == 202
    )
    token = delivered[0].split("#", 1)[1]
    with app.state.session_factory() as database:
        magic = database.scalar(select(MagicLinkToken))
        assert magic is not None
        magic.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        database.commit()
    assert (
        client.post(
            "/v1/auth/magic-links/exchange",
            json={"token": token},
        ).status_code
        == 401
    )

    def fail_delivery(_email: str, _link: str) -> None:
        raise RuntimeError("synthetic SMTP failure")

    failing_app = create_app(
        auth_settings(tmp_path, database_name="failing.db"),
        magic_link_sender=fail_delivery,
        create_tables=True,
    )
    failing_client = TestClient(failing_app)
    response = failing_client.post(
        "/v1/auth/magic-links",
        json={"email": "person@example.com"},
    )
    assert response.status_code == 503
    assert "synthetic" not in response.text
    with failing_app.state.session_factory() as database:
        failure = database.scalar(
            select(AuditEvent).where(
                AuditEvent.event_type == "magic_link_delivery_failed"
            )
        )
        assert failure is not None
        assert failure.details == {"error_type": "RuntimeError"}


def auth_settings(
    tmp_path: Path,
    *,
    database_name: str = "auth.db",
) -> Settings:
    return Settings(
        auth_mode="magic_link",
        auth_token_pepper="test-pepper-that-is-longer-than-32-characters",
        database_url=f"sqlite:///{tmp_path / database_name}",
        storage_path=tmp_path / "artifacts",
        server_key_id="server-test",
        server_seed_hex=SERVER_SEED,
        public_base_url="http://testserver",
    )
