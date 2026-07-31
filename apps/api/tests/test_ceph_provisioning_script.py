from __future__ import annotations

import json
import runpy
import stat
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from botocore.exceptions import ClientError


def test_retention_policy_rejects_unsafe_values() -> None:
    script = runpy.run_path("scripts/provision-ceph-bucket")
    retention_days = cast(Callable[[str, str], int], script["retention_days"])

    assert retention_days("test", "1") == 1
    assert retention_days("staging", "90") == 90
    assert retention_days("production", "365") == 365
    with pytest.raises(ValueError, match="exactly one day"):
        retention_days("test", "2")
    with pytest.raises(ValueError, match="at least 90 days"):
        retention_days("production", "89")
    with pytest.raises(ValueError, match="test, staging or production"):
        retention_days("development", "1")


def test_provisioning_requires_https_ceph_origin() -> None:
    script = runpy.run_path("scripts/provision-ceph-bucket")
    validate_endpoint = cast(Callable[[str], str], script["validate_ceph_endpoint"])

    assert validate_endpoint("https://rgw.example.test/") == "https://rgw.example.test"
    for invalid in (
        "http://rgw.example.test",
        "https://user:secret@rgw.example.test",
        "https://rgw.example.test/path",
        "https://rgw.example.test?query=1",
    ):
        with pytest.raises(ValueError, match="HTTPS origin"):
            validate_endpoint(invalid)


def test_provisioning_creates_and_verifies_new_locked_bucket(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = runpy.run_path("scripts/provision-ceph-bucket")
    main = cast(Callable[[], int], script["main"])
    client = FakeProvisioningClient()
    output = tmp_path / "ceph-provisioning.json"
    environment = {
        "CHITAOZINHO_PROVISION_CEPH_BUCKET": "I_ACCEPT_NEW_IMMUTABLE_BUCKET",
        "CHITAOZINHO_STORAGE_PROVIDER": "ceph",
        "CHITAOZINHO_ENV": "test",
        "CHITAOZINHO_RETENTION_DAYS": "1",
        "CHITAOZINHO_S3_BUCKET": "synthetic-acceptance",
        "CHITAOZINHO_S3_REGION": "ceph",
        "CHITAOZINHO_S3_KMS_KEY_ID": "chitaozinho-evidence",
        "CHITAOZINHO_S3_ENDPOINT_URL": "https://rgw.example.test",
        "CHITAOZINHO_S3_ACCESS_KEY_ID": "synthetic-access",
        "CHITAOZINHO_S3_SECRET_ACCESS_KEY": "synthetic-secret",
    }
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(script["boto3"], "client", lambda *args, **kwargs: client)
    monkeypatch.setattr(
        sys,
        "argv",
        ["provision-ceph-bucket", "--output", str(output)],
    )

    assert main() == 0

    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    report = json.loads(output.read_text())
    assert report["status"] == "complete"
    assert report["versioning"] == "Enabled"
    assert report["retention"] == {"mode": "COMPLIANCE", "days": 1}
    assert client.created_with_lock is True
    assert client.versioning == {"Status": "Enabled"}
    assert client.lock["Rule"]["DefaultRetention"] == {
        "Mode": "COMPLIANCE",
        "Days": 1,
    }
    assert client.encryption["Rules"][0]["ApplyServerSideEncryptionByDefault"] == {
        "SSEAlgorithm": "aws:kms",
        "KMSMasterKeyID": "chitaozinho-evidence",
    }


class FakeProvisioningClient:
    def __init__(self) -> None:
        self.created_with_lock = False
        self.versioning: dict[str, Any] = {}
        self.lock: dict[str, Any] = {}
        self.encryption: dict[str, Any] = {}

    def head_bucket(self, **_: Any) -> None:
        raise ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "synthetic missing bucket"}},
            "HeadBucket",
        )

    def create_bucket(self, **arguments: Any) -> None:
        self.created_with_lock = arguments["ObjectLockEnabledForBucket"] is True

    def put_bucket_versioning(self, **arguments: Any) -> None:
        self.versioning = arguments["VersioningConfiguration"]

    def put_object_lock_configuration(self, **arguments: Any) -> None:
        self.lock = arguments["ObjectLockConfiguration"]

    def put_bucket_encryption(self, **arguments: Any) -> None:
        self.encryption = arguments["ServerSideEncryptionConfiguration"]

    def get_bucket_versioning(self, **_: Any) -> dict[str, Any]:
        return self.versioning

    def get_object_lock_configuration(self, **_: Any) -> dict[str, Any]:
        return {"ObjectLockConfiguration": self.lock}

    def get_bucket_encryption(self, **_: Any) -> dict[str, Any]:
        return {"ServerSideEncryptionConfiguration": self.encryption}
