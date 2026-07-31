from __future__ import annotations

import json
import ssl
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

METRICS_TOKEN = "m" * 32


class PublicEnvironmentHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/healthz":
            self.respond(200, b'{"status":"ok"}', "application/json")
        elif self.path == "/readyz":
            self.respond(200, b'{"status":"ready"}', "application/json")
        elif self.path == "/metrics":
            if self.headers.get("Authorization") != f"Bearer {METRICS_TOKEN}":
                self.respond(
                    401,
                    b'{"detail":"authentication required"}',
                    "application/json",
                    {"WWW-Authenticate": "Bearer"},
                )
            else:
                self.respond(
                    200,
                    (b"chitaozinho_http_requests_total 1\nchitaozinho_jobs_stale_running 0\n"),
                    "text/plain",
                )
        elif self.path == "/v1/auth/session":
            self.respond(200, b'{"authenticated":false}', "application/json")
        elif self.path.startswith("/v1/sessions/"):
            self.respond(401, b'{"detail":"authentication required"}', "application/json")
        else:
            self.respond(404, b"{}", "application/json")

    def respond(
        self,
        status: int,
        body: bytes,
        content_type: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_arguments) -> None:
        return


def test_public_environment_checker_uses_real_tls_and_read_only_probes(
    tmp_path: Path,
) -> None:
    certificate = tmp_path / "certificate.pem"
    private_key = tmp_path / "private-key.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(private_key),
            "-out",
            str(certificate),
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost",
        ],
        check=True,
        capture_output=True,
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), PublicEnvironmentHandler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certificate, private_key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    report_path = tmp_path / "public-environment.json"
    try:
        result = subprocess.run(
            [
                "python",
                "scripts/check-public-environment.py",
                "--base-url",
                f"https://localhost:{server.server_port}",
                "--metrics-token",
                METRICS_TOKEN,
                "--ca-file",
                str(certificate),
                "--output",
                str(report_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.returncode == 0, result.stderr
    assert "report_sha256=sha256:" in result.stdout
    report = json.loads(report_path.read_text())
    assert report["tls"]["version"] in {"TLSv1.2", "TLSv1.3"}
    assert report["tls"]["legacy_protocols_rejected"] is True
    assert report["checks"]["readyz"]["status"] == 200
    assert report["checks"]["metrics_without_token"]["status"] == 401
    assert report["checks"]["metrics_with_token"]["status"] == 200
    assert report["mutating_requests"] == 0
