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


if __name__ == "__main__":
    main()
