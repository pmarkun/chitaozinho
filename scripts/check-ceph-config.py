#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str) -> dict:
    return json.loads((ROOT / "infra" / "ceph" / name).read_text())


def main() -> None:
    version = load("version.json")
    assert version == {
        "ceph_release": "squid",
        "ceph_version": "19.2.5",
        "image": (
            "quay.io/ceph/ceph@"
            "sha256:1bb011052bc6d347d3418adcbf7d88156860d45697bc6323594a11410084064b"
        ),
    }

    service = load("rgw-service.json")
    assert service["service_type"] == "rgw"
    assert service["service_id"] == "chitaozinho-evidence"
    assert service["placement"] == {"label": "rgw", "count_per_host": 1}
    assert service["config"] == {
        "rgw_crypt_require_ssl": "true",
        "rgw_crypt_s3_kms_backend": "vault",
    }
    assert service["spec"] == {
        "rgw_frontend_type": "beast",
        "rgw_frontend_port": 443,
        "ssl": True,
    }

    policy = load("security-policy.json")
    assert policy["bucket"] == {
        "object_lock": True,
        "retention_mode": "COMPLIANCE",
        "test_retention_days": 1,
        "minimum_runtime_retention_days": 90,
        "versioning": True,
    }
    assert policy["encryption"] == {
        "protocol_algorithm": "aws:kms",
        "rgw_kms_backend": "vault",
        "require_tls": True,
    }
    assert all(policy["operations"].values())


if __name__ == "__main__":
    main()
