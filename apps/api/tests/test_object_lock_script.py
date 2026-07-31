from __future__ import annotations

import json
import runpy
import stat
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from botocore.exceptions import ClientError


def test_object_lock_report_is_private_exclusive_and_atomically_updated(
    tmp_path: Path,
) -> None:
    script = runpy.run_path("scripts/test-s3-object-lock")
    create_report = cast(
        Callable[[Path, dict[str, Any]], None],
        script["create_report"],
    )
    replace_report = cast(
        Callable[[Path, dict[str, Any]], bytes],
        script["replace_report"],
    )
    report_path = tmp_path / "report.json"

    create_report(report_path, {"status": "started"})
    assert stat.S_IMODE(report_path.stat().st_mode) == 0o600
    assert json.loads(report_path.read_text()) == {"status": "started"}

    with pytest.raises(FileExistsError):
        create_report(report_path, {"status": "unexpected-overwrite"})

    encoded = replace_report(
        report_path,
        {
            "objects": [{"key": "acceptance/run/manifest.json"}],
            "status": "retaining",
        },
    )
    assert report_path.read_bytes() == encoded
    assert json.loads(encoded)["status"] == "retaining"
    assert list(tmp_path.glob(".*.tmp")) == []


def test_object_lock_acceptance_requires_an_https_ceph_origin() -> None:
    script = runpy.run_path("scripts/test-s3-object-lock")
    validate_endpoint = cast(
        Callable[[str], str],
        script["validate_ceph_endpoint"],
    )

    assert validate_endpoint("https://rgw.example.test/") == ("https://rgw.example.test")
    for invalid in (
        "http://rgw.example.test",
        "https://user:secret@rgw.example.test",
        "https://rgw.example.test/path",
        "https://rgw.example.test?query=1",
    ):
        with pytest.raises(ValueError, match="HTTPS origin"):
            validate_endpoint(invalid)


def test_object_lock_acceptance_exercises_all_storage_guards(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = runpy.run_path("scripts/test-s3-object-lock")
    main = cast(Callable[[], int], script["main"])
    artifact_names = set(cast(dict[str, bytes], script["ARTIFACTS"]))
    client = FakeCephObjectLockClient()
    output = tmp_path / "object-lock-report.json"

    environment = {
        "CHITAOZINHO_RUN_OBJECT_LOCK_TEST": "I_ACCEPT_24H_RETENTION",
        "CHITAOZINHO_STORAGE_PROVIDER": "ceph",
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
        ["test-s3-object-lock", "--output", str(output)],
    )

    assert main() == 0

    report = json.loads(output.read_text())
    assert report["status"] == "complete"
    assert report["versioning"] == "Enabled"
    assert report["object_lock"] == {
        "mode": "COMPLIANCE",
        "default_retention_days": 1,
    }
    assert report["overwrite_refused"] is True
    assert report["early_version_delete_refused"] is True
    assert report["retention_reduction_refused"] is True
    assert {item["name"] for item in report["objects"]} == artifact_names
    assert client.created_names == artifact_names
    assert client.delete_attempts == 1
    assert client.retention_reduction_attempts == 1


class FakeCephObjectLockClient:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict[str, Any]] = {}
        self.created_names: set[str] = set()
        self.delete_attempts = 0
        self.retention_reduction_attempts = 0

    def get_bucket_versioning(self, **_: Any) -> dict[str, str]:
        return {"Status": "Enabled"}

    def get_object_lock_configuration(self, **_: Any) -> dict[str, Any]:
        return {
            "ObjectLockConfiguration": {
                "ObjectLockEnabled": "Enabled",
                "Rule": {
                    "DefaultRetention": {
                        "Mode": "COMPLIANCE",
                        "Days": 1,
                    }
                },
            }
        }

    def put_object(self, **arguments: Any) -> dict[str, str]:
        if arguments["Body"] == b"changed synthetic content":
            raise client_error("PreconditionFailed")
        key = cast(str, arguments["Key"])
        name = key.split("/", 2)[-1]
        version_id = f"version-{len(self.objects) + 1}"
        self.created_names.add(name)
        self.objects[(key, version_id)] = {
            "ObjectLockMode": arguments["ObjectLockMode"],
            "ObjectLockRetainUntilDate": arguments["ObjectLockRetainUntilDate"],
            "ServerSideEncryption": arguments["ServerSideEncryption"],
            "SSEKMSKeyId": arguments["SSEKMSKeyId"],
            "Metadata": arguments["Metadata"],
        }
        return {"VersionId": version_id}

    def head_object(self, **arguments: Any) -> dict[str, Any]:
        return self.objects[(arguments["Key"], arguments["VersionId"])]

    def delete_object(self, **_: Any) -> None:
        self.delete_attempts += 1
        raise client_error("AccessDenied")

    def put_object_retention(self, **arguments: Any) -> None:
        assert arguments["Retention"]["Mode"] == "COMPLIANCE"
        assert arguments["Retention"]["RetainUntilDate"] < datetime.now(UTC) + timedelta(minutes=6)
        self.retention_reduction_attempts += 1
        raise client_error("AccessDenied")


def client_error(code: str) -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": "synthetic refusal"}},
        "SyntheticOperation",
    )
