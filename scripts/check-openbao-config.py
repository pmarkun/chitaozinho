#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    policy = (ROOT / "infra/openbao/signing-runtime-policy.hcl").read_text()
    assert policy.count("path ") == 2
    assert 'path "transit/keys/chitaozinho-server"' in policy
    assert 'path "transit/sign/chitaozinho-server"' in policy
    assert policy.count('capabilities = ["read"]') == 1
    assert policy.count('capabilities = ["update"]') == 1
    forbidden = ("create", "delete", "sudo", "transit/keys/*", 'capabilities = ["*"]')
    assert all(value not in policy for value in forbidden)

    image = (ROOT / "Dockerfile.openbao").read_text()
    assert (
        "ghcr.io/openbao/openbao@sha256:"
        "11fd73a2102cda9c55d5d881a8c3210303146a7ec1e8ac76f526e175c6d24641"
    ) in image
    entrypoint = (ROOT / "infra/openbao/railway-entrypoint.sh").read_text()
    readiness = (ROOT / "infra/openbao/readiness-server.sh").read_text()
    assert '"path": "/openbao/data/raft"' in entrypoint
    assert '"tls_min_version": "tls13"' in entrypoint
    assert '"file_path": "stdout"' in entrypoint
    assert '"audit": [' in entrypoint
    assert "OPENBAO_TLS_CERT_PEM is required" in entrypoint
    assert "OPENBAO_TLS_KEY_PEM is required" in entrypoint
    assert "chitaozinho-openbao-readiness" in entrypoint
    assert 'https://127.0.0.1:8200/v1/sys/health' in readiness
    assert '503 Service Unavailable' in readiness
    assert 'nc -lk -p "$listen_port" -e "$0"' in readiness


if __name__ == "__main__":
    main()
