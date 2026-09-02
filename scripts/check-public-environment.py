#!/usr/bin/env python3
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import ssl
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    Request,
    build_opener,
)

MAX_RESPONSE_BYTES = 1024 * 1024


class RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, *_arguments, **_keyword_arguments):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify a published Chitaozinho API without mutating it."
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--metrics-token", required=True)
    parser.add_argument("--ca-file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    origin, hostname, port = validate_inputs(
        arguments.base_url,
        arguments.metrics_token,
    )
    context = ssl.create_default_context(
        cafile=str(arguments.ca_file) if arguments.ca_file is not None else None
    )
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    tls = inspect_tls(context, hostname, port)
    reject_legacy_tls(
        hostname,
        port,
        ca_file=arguments.ca_file,
    )
    tls["legacy_protocols_rejected"] = True
    opener = build_opener(RejectRedirects(), HTTPSHandler(context=context))
    checks = {
        "healthz": probe(opener, origin, "/healthz"),
        "readyz": probe(opener, origin, "/readyz"),
        "metrics_without_token": probe(opener, origin, "/metrics"),
        "metrics_with_token": probe(
            opener,
            origin,
            "/metrics",
            authorization=f"Bearer {arguments.metrics_token}",
        ),
        "anonymous_auth_session": probe(opener, origin, "/v1/auth/session"),
        "opaque_session_lookup": probe(
            opener,
            origin,
            "/v1/sessions/public-environment-probe",
        ),
    }
    validate_checks(checks)
    report = {
        "schema_version": "0.1.0",
        "checked_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "origin": origin,
        "tls": tls,
        "checks": {
            name: {
                "status": result["status"],
                "content_type": result["content_type"],
            }
            for name, result in checks.items()
        },
        "mutating_requests": 0,
    }
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True).encode() + b"\n"
    write_new(arguments.output, encoded)
    print(f"report={arguments.output}")
    print(f"report_sha256=sha256:{sha256(encoded).hexdigest()}")
    return 0


def validate_inputs(
    base_url: str,
    metrics_token: str,
) -> tuple[str, str, int]:
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("base URL must be an HTTPS origin without credentials or path")
    if len(metrics_token) < 32:
        raise ValueError("metrics token must contain at least 32 characters")
    port = parsed.port or 443
    origin = f"https://{parsed.hostname}"
    if port != 443:
        origin += f":{port}"
    return origin, parsed.hostname, port


def inspect_tls(
    context: ssl.SSLContext,
    hostname: str,
    port: int,
) -> dict[str, str | bool]:
    with (
        socket.create_connection((hostname, port), timeout=10) as connection,
        context.wrap_socket(
            connection,
            server_hostname=hostname,
        ) as secured,
    ):
        version = secured.version()
        cipher = secured.cipher()
        certificate = secured.getpeercert()
    if version not in {"TLSv1.2", "TLSv1.3"}:
        raise RuntimeError(f"unexpected negotiated TLS version: {version}")
    if cipher is None or not certificate.get("notAfter"):
        raise RuntimeError("TLS peer did not provide cipher and certificate validity")
    not_after = datetime.fromtimestamp(
        ssl.cert_time_to_seconds(certificate["notAfter"]),
        tz=UTC,
    )
    if not_after <= datetime.now(UTC):
        raise RuntimeError("TLS certificate is expired")
    return {
        "version": version,
        "cipher": cipher[0],
        "certificate_not_after": not_after.isoformat().replace("+00:00", "Z"),
    }


def reject_legacy_tls(
    hostname: str,
    port: int,
    *,
    ca_file: Path | None,
) -> None:
    context = ssl.create_default_context(cafile=str(ca_file) if ca_file is not None else None)
    context.minimum_version = ssl.TLSVersion.TLSv1
    context.maximum_version = ssl.TLSVersion.TLSv1_1
    try:
        context.set_ciphers("ALL:@SECLEVEL=0")
    except ssl.SSLError as error:
        raise RuntimeError("local TLS runtime cannot probe legacy protocol rejection") from error
    try:
        with (
            socket.create_connection((hostname, port), timeout=10) as connection,
            context.wrap_socket(connection, server_hostname=hostname),
        ):
            pass
    except ssl.SSLError:
        return
    raise RuntimeError("TLS peer accepted TLS 1.0 or TLS 1.1")


def probe(
    opener,
    origin: str,
    path: str,
    *,
    authorization: str | None = None,
) -> dict[str, object]:
    headers = {"Accept": "application/json, text/plain"}
    if authorization is not None:
        headers["Authorization"] = authorization
    request = Request(f"{origin}{path}", headers=headers)
    try:
        with opener.open(request, timeout=10) as response:
            status = response.status
            response_headers = response.headers
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        status = error.code
        response_headers = error.headers
        body = error.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise RuntimeError(f"response too large for {path}")
    return {
        "status": status,
        "content_type": response_headers.get_content_type(),
        "www_authenticate": response_headers.get("WWW-Authenticate"),
        "body": body,
    }


def validate_checks(checks: dict[str, dict[str, object]]) -> None:
    if checks["healthz"]["status"] != 200 or decode_json(checks["healthz"]["body"]) != {
        "status": "ok"
    }:
        raise RuntimeError("/healthz did not report ok")
    if checks["readyz"]["status"] != 200 or decode_json(checks["readyz"]["body"]) != {
        "status": "ready"
    }:
        raise RuntimeError("/readyz did not report ready")
    unauthenticated_metrics = checks["metrics_without_token"]
    if (
        unauthenticated_metrics["status"] != 401
        or unauthenticated_metrics["www_authenticate"] != "Bearer"
    ):
        raise RuntimeError("/metrics accepted a request without its bearer token")
    authenticated_metrics = checks["metrics_with_token"]
    metrics_body = authenticated_metrics["body"]
    if (
        authenticated_metrics["status"] != 200
        or not isinstance(metrics_body, bytes)
        or b"chitaozinho_http_requests_total" not in metrics_body
        or b"chitaozinho_jobs_stale_running" not in metrics_body
    ):
        raise RuntimeError("authenticated /metrics response is incomplete")
    if checks["anonymous_auth_session"]["status"] != 200 or decode_json(
        checks["anonymous_auth_session"]["body"]
    ) != {"authenticated": False}:
        raise RuntimeError("anonymous authentication state is not explicit")
    if checks["opaque_session_lookup"]["status"] != 401:
        raise RuntimeError("anonymous session lookup was not rejected")


def decode_json(value: object) -> object:
    if not isinstance(value, bytes):
        raise ValueError("response body is not bytes")
    return json.loads(value)


def write_new(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(content)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"Public environment check failed: {error}", file=sys.stderr)
        sys.exit(1)
